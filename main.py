import os
import logging
import uuid
import json
from datetime import datetime, timedelta, date, time
from typing import Optional, List, Dict, Any, Tuple, TypedDict, Annotated
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

# LangChain imports - Fixed for compatibility
try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.output_parsers import StrOutputParser
    from pydantic import BaseModel, Field
    from langchain_core.tools import tool
    from langchain_core.memory import BaseMemory
    from langchain_core.language_models import BaseChatModel
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    
    # Import official LangChain AWS package
    from langchain_aws import ChatBedrock
    LANGCHAIN_AVAILABLE = True
    print("✅ LangChain Core: Available")
except ImportError as e:
    print(f"⚠️  LangChain Core: Some modules not available - {e}")
    LANGCHAIN_AVAILABLE = False
    print("❌ LangChain Core: Not available")

# Try importing LangGraph components
try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
    print("✅ LangGraph: Available")
except ImportError as e:
    LANGGRAPH_AVAILABLE = False
    print(f"⚠️  LangGraph: Not available - {e}")

# Try importing Redis chat history
try:
    from langchain_community.chat_message_histories import RedisChatMessageHistory
    REDIS_CHAT_HISTORY_AVAILABLE = True
    print("✅ Redis Chat History: Available")
except ImportError as e:
    REDIS_CHAT_HISTORY_AVAILABLE = False
    print(f"⚠️  Redis Chat History: Not available - {e}")

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

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'hospital'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'port': os.getenv('DB_PORT', 5432)
}

# Redis configuration with safe type conversion
def safe_int_conversion(value, default=0):
    """Safely convert a string to int with fallback to default"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        logger.warning(f"Invalid integer value '{value}', using default {default}")
        return default

REDIS_CONFIG = {
    'url': f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}",
    'password': os.getenv('REDIS_PASSWORD'),
    'db': safe_int_conversion(os.getenv('REDIS_DB'), 0)
}

# Try importing AWS Bedrock
try:
    import boto3
    # Check if AWS credentials are available
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    if aws_access_key and aws_secret_key:
        bedrock_runtime = boto3.client(
            'bedrock-runtime', 
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        BEDROCK_AVAILABLE = True
        logger.info("✅ AWS Bedrock: Available")
    else:
        # Try using default credentials (AWS CLI, IAM roles, etc.)
        bedrock_runtime = boto3.client('bedrock-runtime', region_name=aws_region)
        BEDROCK_AVAILABLE = True
        logger.info("✅ AWS Bedrock: Available (using default credentials)")
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

# ============================================================================
# LangChain Models and Memory Setup
# ============================================================================

class ConversationState(TypedDict):
    """State for conversation management"""
    messages: List[Dict[str, Any]]
    patient_name: Optional[str]
    date_of_birth: Optional[str]
    specialization: Optional[str]
    doctor_preference: Optional[str]
    preferred_date: Optional[str]
    preferred_time: Optional[str]
    booking_intent: bool
    session_id: str

class AppointmentDetails(BaseModel):
    """Pydantic model for appointment details"""
    patient_name: str = Field(description="Full name of the patient")
    date_of_birth: str = Field(description="Date of birth in MM/DD/YYYY format")
    doctor_preference: Optional[str] = Field(default=None, description="Preferred doctor name")
    specialization: Optional[str] = Field(default="General Medicine", description="Medical specialization")
    preferred_date: Optional[str] = Field(default=None, description="Preferred appointment date")
    preferred_time: Optional[str] = Field(default=None, description="Preferred appointment time")
    reason: str = Field(default="General consultation", description="Reason for visit")

class DatabaseContext(BaseModel):
    """Database context for AI responses"""
    doctors: List[Dict[str, Any]] = Field(default_factory=list)
    departments: List[Dict[str, Any]] = Field(default_factory=list)
    specializations: List[Dict[str, Any]] = Field(default_factory=list)
    recent_appointments: List[Dict[str, Any]] = Field(default_factory=list)

def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.debug("Database connection successful")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def serialize_datetime_objects(obj):
    """Convert datetime, date, time, and Decimal objects to strings for JSON serialization"""
    if isinstance(obj, dict):
        return {key: serialize_datetime_objects(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime_objects(item) for item in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, time):
        return obj.strftime('%H:%M:%S')
    elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Decimal':
        return float(obj)
    else:
        return obj

# ============================================================================
# LangChain Tools (Database Operations)
# ============================================================================

@tool
def query_doctor_availability(specialty: str, target_date: str = None) -> str:
    """Query real doctor availability from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return "I'm having trouble accessing our system right now. Let me try again..."
        
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
                # Get available specializations for a more helpful response
                cursor.execute("""
                    SELECT DISTINCT s.name 
                    FROM specializations s 
                    JOIN doctors d ON s.id = d.specialization_id 
                    WHERE d.is_active = TRUE 
                    ORDER BY s.name
                """)
                available_specs = [row['name'] for row in cursor.fetchall()]
                return f"I don't have any doctors listed under {specialty.title()}. However, we have excellent doctors in these specialties: {', '.join(available_specs)}. Would you like me to show you doctors in any of these areas?"
            
            result = f"Great! I found {len(doctors)} excellent doctor{'s' if len(doctors) > 1 else ''} in {specialty.title()}:\n\n"
            
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
                            result += f"- Unfortunately not available on {parsed_date.strftime('%A, %B %d')}\n"
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
                        result += "- Schedule information not available at the moment\n"
                
                result += "\n"
            
            return result
            
    except Exception as e:
        logger.error(f"Error querying doctor availability: {e}")
        return f"Error querying availability: {str(e)}"

@tool
def query_patient_appointments(patient_name: str, date_of_birth: str) -> str:
    """Query real patient appointments from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return "I'm having trouble accessing the appointment system. Let me try again..."
        
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
                return f"I couldn't find any records for {patient_name} with date of birth {date_of_birth}. This could mean:\n\n• You haven't booked with us before\n• The name or date might be slightly different in our records\n\nWould you like me to help you book a new appointment instead?"
            
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
                return f"Good news, {patient_name}! You don't have any upcoming appointments scheduled. Would you like me to help you book one?"
            
            result = f"I found your upcoming appointments, {patient_name}:\n\n"
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

@tool
def reschedule_appointment(appointment_id: int, new_date: str, new_time: str = None) -> str:
    """Reschedule an existing appointment to a new date and time"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Unable to connect to appointment system"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # First, verify the appointment exists and get current details
            cursor.execute("""
                SELECT a.id, a.appointment_date, a.appointment_time, a.patient_id, a.doctor_id,
                       p.first_name as patient_first, p.last_name as patient_last,
                       d.first_name as doctor_first, d.last_name as doctor_last,
                       s.name as specialization
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN doctors d ON a.doctor_id = d.id
                JOIN specializations s ON d.specialization_id = s.id
                WHERE a.id = %s AND a.status NOT IN ('cancelled', 'completed')
            """, (appointment_id,))
            
            appointment = cursor.fetchone()
            if not appointment:
                return f"Appointment #{appointment_id} not found or cannot be rescheduled"
            
            # Parse new date
            try:
                if new_date.lower() in ['today', 'tomorrow']:
                    if new_date.lower() == 'today':
                        new_appointment_date = date.today()
                    else:
                        new_appointment_date = date.today() + timedelta(days=1)
                else:
                    new_appointment_date = dateutil.parser.parse(new_date).date()
            except:
                return "Invalid date format. Please use a clear date format like 'MM/DD/YYYY' or 'tomorrow'"
            
            # Parse new time
            try:
                if new_time:
                    if new_time.lower() in ['morning', 'afternoon', 'evening']:
                        time_preferences = {
                            'morning': time(9, 0),
                            'afternoon': time(14, 0),
                            'evening': time(17, 0)
                        }
                        new_appointment_time = time_preferences[new_time.lower()]
                    else:
                        new_appointment_time = dateutil.parser.parse(new_time).time()
                else:
                    new_appointment_time = appointment['appointment_time']  # Keep current time
            except:
                return "Invalid time format. Please use format like '2:00 PM' or 'morning/afternoon'"
            
            # Check for conflicts with the new slot
            cursor.execute("""
                SELECT id FROM appointments 
                WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s
                AND status NOT IN ('cancelled') AND id != %s
            """, (appointment['doctor_id'], new_appointment_date, new_appointment_time, appointment_id))
            
            if cursor.fetchone():
                return f"The requested time slot is already taken. Please choose a different time."
            
            # Update the appointment
            cursor.execute("""
                UPDATE appointments 
                SET appointment_date = %s, appointment_time = %s, updated_at = %s
                WHERE id = %s
            """, (new_appointment_date, new_appointment_time, datetime.now(), appointment_id))
            
            conn.commit()
            
            success_message = (
                f"✅ Appointment #{appointment_id} rescheduled successfully!\n\n"
                f"Updated Details:\n"
                f"• Patient: {appointment['patient_first']} {appointment['patient_last']}\n"
                f"• Doctor: Dr. {appointment['doctor_first']} {appointment['doctor_last']} ({appointment['specialization']})\n"
                f"• New Date: {new_appointment_date.strftime('%A, %B %d, %Y')}\n"
                f"• New Time: {new_appointment_time.strftime('%I:%M %p')}\n"
                f"• Previous Date: {appointment['appointment_date'].strftime('%A, %B %d, %Y')}\n"
                f"• Previous Time: {appointment['appointment_time'].strftime('%I:%M %p')}"
            )
            
            return success_message
            
    except Exception as e:
        logger.error(f"Error rescheduling appointment: {e}")
        if conn:
            conn.rollback()
        return f"Rescheduling failed: {str(e)}"

@tool
def cancel_appointment(appointment_id: int, cancellation_reason: str = "Patient requested") -> str:
    """Cancel an existing appointment"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Unable to connect to appointment system"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # First, verify the appointment exists and get details
            cursor.execute("""
                SELECT a.id, a.appointment_date, a.appointment_time, a.status,
                       p.first_name as patient_first, p.last_name as patient_last,
                       d.first_name as doctor_first, d.last_name as doctor_last,
                       s.name as specialization
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN doctors d ON a.doctor_id = d.id
                JOIN specializations s ON d.specialization_id = s.id
                WHERE a.id = %s
            """, (appointment_id,))
            
            appointment = cursor.fetchone()
            if not appointment:
                return f"Appointment #{appointment_id} not found"
            
            if appointment['status'] == 'cancelled':
                return f"Appointment #{appointment_id} is already cancelled"
            
            # Cancel the appointment
            cursor.execute("""
                UPDATE appointments 
                SET status = 'cancelled', notes = %s, updated_at = %s
                WHERE id = %s
            """, (f"Cancelled: {cancellation_reason}", datetime.now(), appointment_id))
            
            conn.commit()
            
            success_message = (
                f"❌ Appointment #{appointment_id} cancelled successfully\n\n"
                f"Cancelled Appointment Details:\n"
                f"• Patient: {appointment['patient_first']} {appointment['patient_last']}\n"
                f"• Doctor: Dr. {appointment['doctor_first']} {appointment['doctor_last']} ({appointment['specialization']})\n"
                f"• Date: {appointment['appointment_date'].strftime('%A, %B %d, %Y')}\n"
                f"• Time: {appointment['appointment_time'].strftime('%I:%M %p')}\n"
                f"• Reason: {cancellation_reason}\n\n"
                f"Would you like me to help you book a new appointment?"
            )
            
            return success_message
            
    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        if conn:
            conn.rollback()
        return f"Cancellation failed: {str(e)}"

@tool
def find_earliest_availability(specialization: str = "General Medicine", doctor_preference: str = None, days_ahead: int = 14) -> str:
    """Find the earliest available appointment slots"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Unable to connect to appointment system"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Build doctor query based on preferences
            doctor_condition = ""
            query_params = []
            
            if doctor_preference and doctor_preference.lower() not in ['any', 'no preference']:
                doctor_condition = "AND CONCAT(d.first_name, ' ', d.last_name) ILIKE %s"
                query_params.append(f"%{doctor_preference}%")
            
            # Get available doctors
            cursor.execute(f"""
                SELECT d.id, d.first_name, d.last_name, d.consultation_fee,
                       s.name as specialization
                FROM doctors d
                JOIN specializations s ON d.specialization_id = s.id
                WHERE s.name ILIKE %s AND d.is_active = TRUE {doctor_condition}
                ORDER BY d.last_name, d.first_name
            """, [f"%{specialization}%"] + query_params)
            
            doctors = cursor.fetchall()
            if not doctors:
                return f"No doctors found for {specialization}"
            
            earliest_slots = []
            current_date = date.today()
            end_date = current_date + timedelta(days=days_ahead)
            
            # Check each doctor's availability
            for doctor in doctors:
                cursor.execute("""
                    SELECT da.day_of_week, da.start_time, da.end_time, da.slot_duration
                    FROM doctor_availability da
                    WHERE da.doctor_id = %s AND da.is_active = TRUE
                    ORDER BY da.day_of_week, da.start_time
                """, (doctor['id'],))
                
                availability = cursor.fetchall()
                if not availability:
                    continue
                
                # Find earliest slot for this doctor
                check_date = current_date
                while check_date <= end_date:
                    day_of_week = check_date.weekday() + 1
                    if day_of_week == 7:
                        day_of_week = 0
                    
                    # Check if doctor is available on this day
                    day_availability = [slot for slot in availability if slot['day_of_week'] == day_of_week]
                    
                    for slot in day_availability:
                        slot_start = slot['start_time']
                        slot_duration = slot['slot_duration'] or 30
                        
                        # Check if this slot is already booked
                        cursor.execute("""
                            SELECT id FROM appointments 
                            WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s
                            AND status NOT IN ('cancelled')
                        """, (doctor['id'], check_date, slot_start))
                        
                        if not cursor.fetchone():
                            earliest_slots.append({
                                'doctor': doctor,
                                'date': check_date,
                                'time': slot_start,
                                'duration': slot_duration
                            })
                            break
                    
                    if earliest_slots and earliest_slots[-1]['doctor']['id'] == doctor['id']:
                        break  # Found a slot for this doctor
                    
                    check_date += timedelta(days=1)
            
            if not earliest_slots:
                return f"No available appointments found in the next {days_ahead} days for {specialization}"
            
            # Sort by date and time
            earliest_slots.sort(key=lambda x: (x['date'], x['time']))
            
            result = f"🗓️ Earliest available appointments for {specialization}:\n\n"
            
            for i, slot in enumerate(earliest_slots[:5]):  # Show top 5 earliest
                doctor = slot['doctor']
                result += f"{i+1}. Dr. {doctor['first_name']} {doctor['last_name']}\n"
                result += f"   📅 {slot['date'].strftime('%A, %B %d, %Y')}\n"
                result += f"   🕐 {slot['time'].strftime('%I:%M %p')}\n"
                result += f"   💰 ${doctor['consultation_fee']}\n\n"
            
            result += "Would you like me to book any of these appointments? I'll need your name and date of birth to proceed."
            
            return result
            
    except Exception as e:
        logger.error(f"Error finding earliest availability: {e}")
        return f"Error checking availability: {str(e)}"

@tool
def check_doctor_schedule(doctor_name: str, target_date: str = None, days_ahead: int = 7) -> str:
    """Check a specific doctor's schedule and availability"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Unable to connect to appointment system"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Find the doctor
            cursor.execute("""
                SELECT d.id, d.first_name, d.last_name, d.consultation_fee, d.experience_years,
                       s.name as specialization
                FROM doctors d
                JOIN specializations s ON d.specialization_id = s.id
                WHERE CONCAT(d.first_name, ' ', d.last_name) ILIKE %s AND d.is_active = TRUE
            """, (f"%{doctor_name}%",))
            
            doctor = cursor.fetchone()
            if not doctor:
                return f"Doctor '{doctor_name}' not found. Please check the spelling or try searching by specialty."
            
            result = f"👨‍⚕️ Dr. {doctor['first_name']} {doctor['last_name']} ({doctor['specialization']})\n"
            result += f"Experience: {doctor['experience_years']} years\n"
            result += f"Consultation Fee: ${doctor['consultation_fee']}\n\n"
            
            if target_date:
                # Check specific date
                try:
                    if target_date.lower() in ['today', 'tomorrow']:
                        if target_date.lower() == 'today':
                            check_date = date.today()
                        else:
                            check_date = date.today() + timedelta(days=1)
                    else:
                        check_date = dateutil.parser.parse(target_date).date()
                    
                    day_of_week = check_date.weekday() + 1
                    if day_of_week == 7:
                        day_of_week = 0
                    
                    # Get doctor's availability for that day
                    cursor.execute("""
                        SELECT da.start_time, da.end_time, da.slot_duration
                        FROM doctor_availability da
                        WHERE da.doctor_id = %s AND da.day_of_week = %s AND da.is_active = TRUE
                    """, (doctor['id'], day_of_week))
                    
                    availability = cursor.fetchall()
                    if not availability:
                        result += f"❌ Not available on {check_date.strftime('%A, %B %d, %Y')}"
                        return result
                    
                    result += f"📅 Availability on {check_date.strftime('%A, %B %d, %Y')}:\n"
                    
                    for slot in availability:
                        start_time = slot['start_time']
                        end_time = slot['end_time']
                        
                        # Check existing appointments
                        cursor.execute("""
                            SELECT appointment_time FROM appointments 
                            WHERE doctor_id = %s AND appointment_date = %s 
                            AND status NOT IN ('cancelled')
                            ORDER BY appointment_time
                        """, (doctor['id'], check_date))
                        
                        booked_times = [apt['appointment_time'] for apt in cursor.fetchall()]
                        
                        result += f"\n🕐 {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}\n"
                        
                        if booked_times:
                            result += "   Booked slots:\n"
                            for booked_time in booked_times:
                                if start_time <= booked_time <= end_time:
                                    result += f"   ❌ {booked_time.strftime('%I:%M %p')}\n"
                        
                        # Show available slots
                        result += "   Available slots:\n"
                        current_time = start_time
                        slot_duration = slot['slot_duration'] or 30
                        
                        while current_time < end_time:
                            if current_time not in booked_times:
                                result += f"   ✅ {current_time.strftime('%I:%M %p')}\n"
                            
                            current_time = (datetime.combine(date.today(), current_time) + 
                                          timedelta(minutes=slot_duration)).time()
                
                except Exception as e:
                    result += f"Error parsing date: {str(e)}"
            
            else:
                # Show general weekly schedule
                cursor.execute("""
                    SELECT da.day_of_week, da.start_time, da.end_time
                    FROM doctor_availability da
                    WHERE da.doctor_id = %s AND da.is_active = TRUE
                    ORDER BY da.day_of_week, da.start_time
                """, (doctor['id'],))
                
                weekly_availability = cursor.fetchall()
                if weekly_availability:
                    result += "📅 Weekly Schedule:\n"
                    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
                    
                    for slot in weekly_availability:
                        day_name = day_names[slot['day_of_week']]
                        start_time = slot['start_time'].strftime('%I:%M %p')
                        end_time = slot['end_time'].strftime('%I:%M %p')
                        result += f"• {day_name}: {start_time} - {end_time}\n"
                
                result += f"\nWould you like to check availability for a specific date or book an appointment?"
            
            return result
            
    except Exception as e:
        logger.error(f"Error checking doctor schedule: {e}")
        return f"Error checking schedule: {str(e)}"

@tool
def search_doctors_by_condition(medical_condition: str, patient_age: int = None) -> str:
    """Find doctors best suited for a specific medical condition"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Unable to connect to doctor database"
        
        # Medical condition to specialty mapping
        condition_specialties = {
            'heart': ['Cardiology'],
            'chest pain': ['Cardiology'],
            'blood pressure': ['Cardiology'],
            'skin': ['Dermatology'],
            'rash': ['Dermatology'],
            'acne': ['Dermatology'],
            'child': ['Pediatrics'],
            'baby': ['Pediatrics'],
            'pregnancy': ['Gynecology'],
            'womens health': ['Gynecology'],
            'bone': ['Orthopedics'],
            'joint': ['Orthopedics'],
            'back pain': ['Orthopedics'],
            'headache': ['Neurology'],
            'migraine': ['Neurology'],
            'mental health': ['Psychiatry'],
            'depression': ['Psychiatry'],
            'anxiety': ['Psychiatry'],
            'eye': ['Ophthalmology'],
            'vision': ['Ophthalmology'],
            'ear': ['ENT'],
            'throat': ['ENT'],
            'nose': ['ENT'],
            'stomach': ['Gastroenterology'],
            'digestive': ['Gastroenterology'],
            'diabetes': ['Endocrinology'],
            'thyroid': ['Endocrinology'],
            'breathing': ['Pulmonology'],
            'cough': ['Pulmonology'],
            'arthritis': ['Rheumatology'],
            'cancer': ['Oncology']
        }
        
        # Find matching specialties
        recommended_specialties = []
        condition_lower = medical_condition.lower()
        
        for condition, specialties in condition_specialties.items():
            if condition in condition_lower:
                recommended_specialties.extend(specialties)
        
        # If no specific match, use General Medicine
        if not recommended_specialties:
            recommended_specialties = ['General Medicine']
        
        # Remove duplicates
        recommended_specialties = list(set(recommended_specialties))
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get doctors for recommended specialties
            specialty_placeholders = ','.join(['%s'] * len(recommended_specialties))
            
            cursor.execute(f"""
                SELECT d.id, d.first_name, d.last_name, d.consultation_fee, d.experience_years,
                       s.name as specialization
                FROM doctors d
                JOIN specializations s ON d.specialization_id = s.id
                WHERE s.name = ANY(%s) AND d.is_active = TRUE
                ORDER BY s.name, d.experience_years DESC, d.last_name
            """, (recommended_specialties,))
            
            doctors = cursor.fetchall()
            
            if not doctors:
                return f"I couldn't find specialists specifically for '{medical_condition}'. Would you like me to show you our General Medicine doctors instead?"
            
            result = f"🏥 Recommended doctors for '{medical_condition}':\n\n"
            
            # Group by specialty
            by_specialty = {}
            for doctor in doctors:
                specialty = doctor['specialization']
                if specialty not in by_specialty:
                    by_specialty[specialty] = []
                by_specialty[specialty].append(doctor)
            
            for specialty, spec_doctors in by_specialty.items():
                result += f"**{specialty}:**\n"
                
                for doctor in spec_doctors[:3]:  # Top 3 per specialty
                    result += f"• Dr. {doctor['first_name']} {doctor['last_name']}\n"
                    result += f"  Experience: {doctor['experience_years']} years\n"
                    result += f"  Consultation Fee: ${doctor['consultation_fee']}\n\n"
                
                if len(spec_doctors) > 3:
                    result += f"  ... and {len(spec_doctors) - 3} more {specialty} doctors\n\n"
            
            # Add age-specific recommendations
            if patient_age is not None:
                if patient_age < 18:
                    result += "💡 Since this is for someone under 18, I'd especially recommend our Pediatrics specialists.\n\n"
                elif patient_age > 65:
                    result += "💡 For patients over 65, our doctors have special experience with age-related care.\n\n"
            
            result += "Would you like to check availability for any of these doctors or book an appointment?"
            
            return result
            
    except Exception as e:
        logger.error(f"Error searching doctors by condition: {e}")
        return f"Error searching doctors: {str(e)}"

@tool
def book_appointment(patient_name: str, date_of_birth: str, specialization: str = "General Medicine", 
                    doctor_preference: str = None, preferred_date: str = None, preferred_time: str = None) -> str:
    """Book an appointment with proper validation"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Database connection error"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Create or find patient
            name_parts = patient_name.strip().split()
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
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
                return "Invalid date format. Please use MM/DD/YYYY or DD/MM/YYYY"
            
            # Check if patient exists
            cursor.execute("""
                SELECT id FROM patients 
                WHERE LOWER(first_name) = LOWER(%s) 
                AND LOWER(last_name) = LOWER(%s) 
                AND date_of_birth = %s
            """, (first_name, last_name, dob))
            
            existing_patient = cursor.fetchone()
            if existing_patient:
                patient_id = existing_patient['id']
            else:
                # Create new patient
                email = f"{first_name.lower()}.{last_name.lower()}@example.com"
                cursor.execute("""
                    INSERT INTO patients (first_name, last_name, email, date_of_birth, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (first_name, last_name, email, dob, datetime.now()))
                
                patient_id = cursor.fetchone()['id']
            
            # Find doctor
            doctor_id = None
            if doctor_preference and not doctor_preference.lower() in ['any', 'no preference']:
                # Search by doctor name
                cursor.execute("""
                    SELECT d.id, d.first_name, d.last_name, s.name as specialization
                    FROM doctors d
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE CONCAT(d.first_name, ' ', d.last_name) ILIKE %s
                    AND d.is_active = TRUE
                """, (f"%{doctor_preference}%",))
                
                doctor = cursor.fetchone()
                if doctor:
                    doctor_id = doctor['id']
            
            # If no specific doctor found, find by specialization
            if not doctor_id:
                cursor.execute("""
                    SELECT d.id, d.first_name, d.last_name, s.name as specialization
                    FROM doctors d
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE s.name ILIKE %s AND d.is_active = TRUE
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (f"%{specialization}%",))
                
                doctor = cursor.fetchone()
                if doctor:
                    doctor_id = doctor['id']
            
            if not doctor_id:
                return f"No available doctors found for {specialization}"
            
            # Parse preferred date
            try:
                if preferred_date and preferred_date.lower() in ['today', 'tomorrow']:
                    if preferred_date.lower() == 'today':
                        appointment_date = date.today()
                    else:
                        appointment_date = date.today() + timedelta(days=1)
                elif preferred_date:
                    appointment_date = dateutil.parser.parse(preferred_date).date()
                else:
                    appointment_date = date.today() + timedelta(days=1)
            except:
                appointment_date = date.today() + timedelta(days=1)
            
            # Parse preferred time
            try:
                if preferred_time and preferred_time.lower() in ['morning', 'afternoon', 'evening']:
                    time_preferences = {
                        'morning': time(9, 0),
                        'afternoon': time(14, 0),
                        'evening': time(17, 0)
                    }
                    appointment_time = time_preferences[preferred_time.lower()]
                elif preferred_time:
                    appointment_time = dateutil.parser.parse(preferred_time).time()
                else:
                    appointment_time = time(10, 0)  # Default to 10 AM
            except:
                appointment_time = time(10, 0)
            
            # Check for conflicts
            cursor.execute("""
                SELECT id FROM appointments 
                WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s
                AND status NOT IN ('cancelled')
            """, (doctor_id, appointment_date, appointment_time))
            
            if cursor.fetchone():
                return "Time slot is already booked"
            
            # Create appointment
            cursor.execute("""
                INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, 
                                        status, reason_for_visit, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                patient_id, doctor_id, appointment_date, appointment_time,
                'scheduled', 'General consultation', datetime.now()
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
                f"• Patient: {patient_name}\n"
                f"• Doctor: Dr. {doctor_info['first_name']} {doctor_info['last_name']} ({doctor_info['specialization']})\n"
                f"• Date: {appointment_date.strftime('%A, %B %d, %Y')}\n"
                f"• Time: {appointment_time.strftime('%I:%M %p')}\n"
                f"• Consultation Fee: ${doctor_info['consultation_fee']}\n"
                f"• Reason: General consultation"
            )
            
            return success_message
            
    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        if conn:
            conn.rollback()
        return f"Booking failed: {str(e)}"

# ============================================================================
# LangChain Memory and State Management
# ============================================================================

class HospitalMemory:
    """Custom memory for hospital conversation state"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages = []
        self.state = {
            'patient_name': None,
            'date_of_birth': None,
            'specialization': None,
            'doctor_preference': None,
            'preferred_date': None,
            'preferred_time': None,
            'booking_intent': False
        }
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_history": self.messages,
            "patient_name": self.state.get('patient_name'),
            "date_of_birth": self.state.get('date_of_birth'),
            "specialization": self.state.get('specialization'),
            "doctor_preference": self.state.get('doctor_preference'),
            "preferred_date": self.state.get('preferred_date'),
            "preferred_time": self.state.get('preferred_time'),
            "booking_intent": self.state.get('booking_intent')
        }
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        # Save messages
        if "messages" in inputs:
            self.messages = inputs["messages"]
        
        # Update state based on outputs
        if "patient_name" in outputs:
            self.state["patient_name"] = outputs["patient_name"]
        if "date_of_birth" in outputs:
            self.state["date_of_birth"] = outputs["date_of_birth"]
        if "specialization" in outputs:
            self.state["specialization"] = outputs["specialization"]
        if "doctor_preference" in outputs:
            self.state["doctor_preference"] = outputs["doctor_preference"]
        if "preferred_date" in outputs:
            self.state["preferred_date"] = outputs["preferred_date"]
        if "preferred_time" in outputs:
            self.state["preferred_time"] = outputs["preferred_time"]
        if "booking_intent" in outputs:
            self.state["booking_intent"] = outputs["booking_intent"]
    
    def clear(self) -> None:
        self.messages = []
        self.state = {
            'patient_name': None,
            'date_of_birth': None,
            'specialization': None,
            'doctor_preference': None,
            'preferred_date': None,
            'preferred_time': None,
            'booking_intent': False
        }

# ============================================================================
# Custom LLM using bedrock.py Claude Model
# ============================================================================

class ClaudeBedrockLLM:
    """Custom LLM that uses official LangChain AWS ChatBedrock"""
    
    def __init__(self):
        # Use the official ChatBedrock from langchain-aws
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize ChatBedrock with credentials if available
        if aws_access_key and aws_secret_key:
            self.chat_bedrock = ChatBedrock(
                model="anthropic.claude-3-sonnet-20240229-v1:0",
                region_name=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                beta_use_converse_api=True
            )
        else:
            # Use default credentials
            self.chat_bedrock = ChatBedrock(
                model="anthropic.claude-3-sonnet-20240229-v1:0",
                region_name=aws_region,
                beta_use_converse_api=True
            )
    
    @property
    def _llm_type(self) -> str:
        return "claude_bedrock"
    
    def invoke(self, messages):
        """Generate response using official ChatBedrock"""
        try:
            # Check if tools are bound
            if hasattr(self, 'tools') and self.tools:
                # Use tools-based approach
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_core.output_parsers import StrOutputParser
                
                # Create prompt template
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a helpful AI assistant. Use the available tools when needed."),
                    ("human", "{input}")
                ])
                
                # Create chain with tools
                chain = prompt | self.chat_bedrock.bind_tools(self.tools) | StrOutputParser()
                
                # Extract the last human message
                last_message = None
                for msg in reversed(messages):
                    if hasattr(msg, 'content') and isinstance(msg.content, str):
                        last_message = msg.content
                        break
                
                if last_message:
                    response = chain.invoke({"input": last_message})
                    return response
                else:
                    # Fallback to direct invocation
                    response = self.chat_bedrock.invoke(messages)
                    return response
            else:
                # Direct invocation without tools
                response = self.chat_bedrock.invoke(messages)
                return response
            
        except Exception as e:
            logger.error(f"Error in ClaudeBedrockLLM: {e}")
            # Return a simple object with content attribute
            class SimpleResponse:
                def __init__(self, content):
                    self.content = content
            
            return SimpleResponse("I'm having trouble processing your request. Please try again.")
    
    def __call__(self, messages):
        """Make the class callable for LangChain compatibility"""
        return self.invoke(messages)
    
    def bind(self, **kwargs):
        """Bind parameters for LangChain compatibility"""
        return self
    
    def bind_tools(self, tools):
        """Bind tools to the LLM"""
        # Store tools for use in invoke
        self.tools = tools
        return self

# ============================================================================
# LangChain LLM Setup
# ============================================================================

def get_llm():
    """Get LangChain LLM instance using official ChatBedrock"""
    if BEDROCK_AVAILABLE:
        try:
            llm = ClaudeBedrockLLM()
            logger.info("✅ ClaudeBedrockLLM initialized successfully")
            return llm
        except Exception as e:
            logger.error(f"Error initializing ClaudeBedrockLLM: {e}")
            return None
    else:
        logger.warning("Bedrock not available, using fallback")
        return None

# ============================================================================
# LangGraph State and Nodes
# ============================================================================

class HospitalState(TypedDict):
    """Enhanced state for LangGraph hospital conversation with comprehensive database integration"""
    # Core conversation
    messages: Annotated[List[Dict[str, Any]], "The conversation messages"]
    session_id: Annotated[str, "Session identifier"]
    current_message: Annotated[str, "Current user message"]
    ai_response: Annotated[Optional[str], "AI response"]
    
    # Patient information
    patient_name: Annotated[Optional[str], "Patient's full name"]
    date_of_birth: Annotated[Optional[str], "Patient's date of birth"]
    patient_id: Annotated[Optional[int], "Database patient ID if found"]
    patient_exists: Annotated[bool, "Whether patient exists in database"]
    
    # Appointment preferences
    specialization: Annotated[Optional[str], "Medical specialization"]
    doctor_preference: Annotated[Optional[str], "Preferred doctor"]
    doctor_id: Annotated[Optional[int], "Database doctor ID if found"]
    preferred_date: Annotated[Optional[str], "Preferred appointment date"]
    preferred_time: Annotated[Optional[str], "Preferred appointment time"]
    urgency: Annotated[str, "Appointment urgency: urgent|routine|flexible"]
    reason_for_visit: Annotated[Optional[str], "Reason for the appointment"]
    
    # Intent and workflow
    intent: Annotated[str, "Primary user intent: book|reschedule|cancel|inquiry|availability|greeting"]
    booking_intent: Annotated[bool, "Whether user wants to book"]
    should_book: Annotated[bool, "Whether to attempt booking"]
    requires_clarification: Annotated[List[str], "Items needing clarification"]
    
    # Database query results
    available_doctors: Annotated[List[Dict], "Doctors matching criteria"]
    doctor_availability: Annotated[List[Dict], "Available time slots"]
    existing_appointments: Annotated[List[Dict], "Patient's existing appointments"]
    appointment_conflicts: Annotated[List[Dict], "Time slot conflicts"]
    
    # Tool tracking and decisions
    tools_used: Annotated[List[str], "Tools used in this turn"]
    database_queries_performed: Annotated[List[str], "Database queries executed"]
    needs_database_check: Annotated[bool, "Whether database check is needed"]
    ready_for_booking: Annotated[bool, "All required info gathered for booking"]
    
    # Context and enhancement
    conversation_context: Annotated[Dict[str, Any], "Rich conversation context"]
    db_context: Annotated[Dict[str, Any], "Current database context"]
    last_tool_result: Annotated[Optional[str], "Result from last tool execution"]
    confidence_score: Annotated[float, "Confidence in extracted information"]

def extract_appointment_details(state: HospitalState) -> HospitalState:
    """Extract appointment details using enhanced AI-powered analysis"""
    message = state["current_message"]
    
    # Use the enhanced Claude model for intelligent extraction
    from bedrock import analyze_appointment_intent
    
    try:
        # Get enhanced context for better analysis
        db_context = get_current_db_context()
        enhanced_context = f"""
CURRENT DATABASE CONTEXT:
Available Specializations: {', '.join([s['name'] for s in db_context.get('specializations', [])])}
Active Doctors: {len(db_context.get('doctors', []))}

CONVERSATION HISTORY:
{format_conversation_context(state.get('messages', []))}
"""
        
        # Use AI to analyze intent and extract information
        intent_result = analyze_appointment_intent(message, enhanced_context)
        intent_data = json.loads(intent_result)
        
        # Update state with AI-extracted information
        state["intent"] = intent_data.get("intent", "unclear")
        state["confidence_score"] = intent_data.get("confidence", 0.0)
        state["requires_clarification"] = intent_data.get("requires_clarification", [])
        
        # Extract patient information
        extracted_info = intent_data.get("extracted_info", {})
        if extracted_info.get("patient_name") and not state.get("patient_name"):
            state["patient_name"] = extracted_info["patient_name"]
        if extracted_info.get("date_of_birth") and not state.get("date_of_birth"):
            state["date_of_birth"] = extracted_info["date_of_birth"]
        
        # Extract appointment preferences
        preferences = intent_data.get("appointment_preferences", {})
        if preferences.get("specialty") and not state.get("specialization"):
            state["specialization"] = preferences["specialty"]
        if preferences.get("doctor_name") and not state.get("doctor_preference"):
            state["doctor_preference"] = preferences["doctor_name"]
        if preferences.get("preferred_date") and not state.get("preferred_date"):
            state["preferred_date"] = preferences["preferred_date"]
        if preferences.get("preferred_time") and not state.get("preferred_time"):
            state["preferred_time"] = preferences["preferred_time"]
        if preferences.get("urgency"):
            state["urgency"] = preferences["urgency"]
        
        # Set booking intent
        booking_intents = ["book_appointment", "reschedule", "cancel"]
        state["booking_intent"] = state["intent"] in booking_intents
        
        # Check if database validation is needed
        state["needs_database_check"] = (
            state.get("patient_name") and state.get("date_of_birth") and
            state["intent"] in ["inquiry", "book_appointment", "reschedule", "cancel"]
        )
        
        # Initialize default values for new state fields
        state.setdefault("patient_exists", False)
        state.setdefault("patient_id", None)
        state.setdefault("doctor_id", None)
        state.setdefault("available_doctors", [])
        state.setdefault("doctor_availability", [])
        state.setdefault("existing_appointments", [])
        state.setdefault("appointment_conflicts", [])
        state.setdefault("tools_used", [])
        state.setdefault("database_queries_performed", [])
        state.setdefault("ready_for_booking", False)
        state.setdefault("conversation_context", {})
        state.setdefault("db_context", db_context)
        state.setdefault("last_tool_result", None)
        state.setdefault("urgency", "routine")
        state.setdefault("reason_for_visit", None)
        
    except Exception as e:
        logger.error(f"Error in AI extraction: {e}")
        # Fallback to basic extraction if AI fails
        fallback_extract_basic_info(state, message)
    
    return state

def fallback_extract_basic_info(state: HospitalState, message: str):
    """Fallback basic extraction if AI analysis fails"""
    # Simple pattern-based extraction as backup
    
    # Extract name (basic patterns)
    name_match = re.search(r'(?:name is|i am|i\'m|my name is|this is)\s+([a-zA-Z\s]+)', message, re.IGNORECASE)
    if name_match and not state.get("patient_name"):
        potential_name = name_match.group(1).strip()
        if len(potential_name.split()) >= 2:
            state["patient_name"] = potential_name
    
    # Extract DOB
    dob_match = re.search(r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})\b', message)
    if dob_match and not state.get("date_of_birth"):
        state["date_of_birth"] = dob_match.group(1)
    
    # Extract basic intent
    if any(word in message.lower() for word in ['book', 'schedule', 'appointment']):
        state["intent"] = "book_appointment"
        state["booking_intent"] = True
    elif any(word in message.lower() for word in ['reschedule', 'change', 'move']):
        state["intent"] = "reschedule"
    elif any(word in message.lower() for word in ['cancel', 'delete']):
        state["intent"] = "cancel"
    elif any(word in message.lower() for word in ['check', 'find', 'show', 'my appointments']):
        state["intent"] = "inquiry"
    else:
        state["intent"] = "greeting"
    
    state["confidence_score"] = 0.5  # Low confidence for fallback

def get_current_db_context():
    """Get current database context for AI analysis"""
    try:
        conn = get_db_connection()
        if not conn:
            return {"doctors": [], "specializations": [], "recent_appointments": []}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get specializations
            cursor.execute("SELECT id, name FROM specializations WHERE is_active = TRUE ORDER BY name")
            specializations = [dict(row) for row in cursor.fetchall()]
            
            # Get active doctors count
            cursor.execute("SELECT COUNT(*) as count FROM doctors WHERE is_active = TRUE")
            doctor_count = cursor.fetchone()['count']
            
            # Get recent appointments count
            cursor.execute("""
                SELECT COUNT(*) as count FROM appointments 
                WHERE appointment_date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            recent_count = cursor.fetchone()['count']
            
            return {
                "specializations": specializations,
                "doctors": [{"count": doctor_count}],  # Simplified for context
                "recent_appointments": [{"count": recent_count}]
            }
    except Exception as e:
        logger.error(f"Error getting DB context: {e}")
        return {"doctors": [], "specializations": [], "recent_appointments": []}

def format_conversation_context(messages):
    """Format conversation history for AI context"""
    if not messages:
        return "No previous conversation"
    
    context = "Recent conversation:\n"
    for msg in messages[-3:]:  # Last 3 messages
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:100]  # Truncate for context
        context += f"{role}: {content}\n"
    
    return context

def validate_patient_data(state: HospitalState) -> HospitalState:
    """Validate patient data against database"""
    if not state.get("needs_database_check"):
        return state
    
    patient_name = state.get("patient_name")
    date_of_birth = state.get("date_of_birth")
    
    if not (patient_name and date_of_birth):
        return state
    
    try:
        # Use the existing query_patient_appointments tool for validation
        result = query_patient_appointments(patient_name, date_of_birth)
        state["last_tool_result"] = result
        state["database_queries_performed"].append("patient_lookup")
        
        # Check if patient exists based on result
        if "couldn't find any records" in result.lower():
            state["patient_exists"] = False
            state["existing_appointments"] = []
        else:
            state["patient_exists"] = True
            # Extract appointment information from result if available
            if "upcoming appointments" in result.lower():
                # Patient has appointments - they exist
                state["existing_appointments"] = [{"status": "found_appointments"}]
        
    except Exception as e:
        logger.error(f"Error validating patient data: {e}")
        state["last_tool_result"] = f"Error checking patient information: {str(e)}"
    
    return state

def determine_next_action(state: HospitalState) -> HospitalState:
    """Dynamically determine the next action based on intent and available information"""
    intent = state.get("intent", "unclear")
    confidence = state.get("confidence_score", 0.0)
    
    # Reset action flags
    state["should_book"] = False
    state["needs_database_check"] = False
    state["ready_for_booking"] = False
    
    if intent == "book_appointment":
        # Check if we have all required information for booking
        has_name = bool(state.get("patient_name"))
        has_dob = bool(state.get("date_of_birth"))
        has_specialty = bool(state.get("specialization"))
        
        if has_name and has_dob and has_specialty:
            state["ready_for_booking"] = True
            state["should_book"] = True
        elif has_name and has_dob:
            # Need to check availability or get specialty preference
            state["needs_database_check"] = True
        else:
            # Need more information - will be handled by generate_response
            pass
    
    elif intent == "inquiry":
        if state.get("patient_name") and state.get("date_of_birth"):
            state["needs_database_check"] = True
    
    elif intent == "availability_check":
        # Check doctor/specialty availability
        state["needs_database_check"] = True
    
    elif intent in ["reschedule", "cancel"]:
        # Need to validate patient and find existing appointments
        if state.get("patient_name") and state.get("date_of_birth"):
            state["needs_database_check"] = True
    
    elif intent == "greeting" or confidence < 0.3:
        # Low confidence or greeting - just generate conversational response
        pass
    
    return state

def execute_database_operations(state: HospitalState) -> HospitalState:
    """Execute appropriate database operations based on intent and state"""
    intent = state.get("intent", "unclear")
    
    if not state.get("needs_database_check"):
        return state
    
    try:
        if intent == "availability_check":
            # Check doctor availability
            specialization = state.get("specialization", "General Medicine")
            doctor_preference = state.get("doctor_preference")
            preferred_date = state.get("preferred_date")
            
            if doctor_preference:
                # Check specific doctor's schedule
                result = check_doctor_schedule(doctor_preference, preferred_date)
                state["tools_used"].append("check_doctor_schedule")
            else:
                # Check general availability
                result = query_doctor_availability(specialization, preferred_date)
                state["tools_used"].append("query_doctor_availability")
            
            state["last_tool_result"] = result
            state["database_queries_performed"].append("availability_check")
        
        elif intent == "inquiry" and state.get("patient_exists"):
            # Patient exists, get their appointments
            result = query_patient_appointments(state["patient_name"], state["date_of_birth"])
            state["last_tool_result"] = result
            state["tools_used"].append("query_patient_appointments")
            state["database_queries_performed"].append("patient_appointments")
        
        elif intent == "book_appointment" and not state.get("ready_for_booking"):
            # Get availability to help with booking decision
            specialization = state.get("specialization", "General Medicine")
            result = find_earliest_availability(specialization, state.get("doctor_preference"))
            state["last_tool_result"] = result
            state["tools_used"].append("find_earliest_availability")
            state["database_queries_performed"].append("earliest_availability")
    
    except Exception as e:
        logger.error(f"Error in database operations: {e}")
        state["last_tool_result"] = f"Error accessing our appointment system: {str(e)}"
    
    return state

def should_attempt_booking(state: HospitalState) -> HospitalState:
    """Enhanced booking decision logic"""
    # Check if all conditions are met for booking
    ready_conditions = [
        state.get("ready_for_booking", False),
        state.get("should_book", False),
        state.get("patient_name"),
        state.get("date_of_birth"),
        state.get("intent") == "book_appointment"
    ]
    
    state["should_book"] = all(ready_conditions)
    
    # Additional validation for booking readiness
    if state["should_book"]:
        # Ensure we have at least a specialty or doctor preference
        if not (state.get("specialization") or state.get("doctor_preference")):
            state["should_book"] = False
            state["requires_clarification"].append("specialty_or_doctor")
    
    return state

def generate_ai_response(state: HospitalState) -> HospitalState:
    """Generate AI response using enhanced Claude with comprehensive database context"""
    from bedrock import get_ai_response
    
    # Get database context and conversation state
    db_context = state.get("db_context", {})
    intent = state.get("intent", "unclear")
    confidence = state.get("confidence_score", 0.0)
    last_tool_result = state.get("last_tool_result")
    requires_clarification = state.get("requires_clarification", [])
    
    # Build comprehensive context for Claude
    context_info = build_comprehensive_context(state)
    
    # Build enhanced system prompt based on intent and state
    system_prompt = f"""You are Claude, an intelligent AI assistant for a modern hospital appointment booking system. You have access to real-time database information and can coordinate actual appointment bookings.

🔍 CURRENT CONVERSATION STATE:
Intent: {intent} (Confidence: {confidence:.1f})
Patient Name: {state.get('patient_name', 'Not provided')}
Date of Birth: {state.get('date_of_birth', 'Not provided')}
Specialization: {state.get('specialization', 'Not specified')}
Doctor Preference: {state.get('doctor_preference', 'None')}
Preferred Date: {state.get('preferred_date', 'Not specified')}
Preferred Time: {state.get('preferred_time', 'Not specified')}

📊 DATABASE CONTEXT:
{context_info}

🚨 ANTI-HALLUCINATION PROTOCOL:
1. ALL specific medical information MUST come from database queries
2. NEVER invent doctor names, appointment times, or availability
3. If you need specific information, clearly state you're checking the database
4. Use ONLY the database tool results provided to you

💬 CONVERSATION GUIDANCE:

For BOOKING APPOINTMENTS:
- Guide users through: Name → DOB → Specialty/Doctor → Date/Time
- Be conversational: "I'd be happy to help! What's your name?"
- Remember information provided earlier
- Confirm details before booking

For AVAILABILITY CHECKS:
- Use real database results only
- Present options clearly with specific times and doctors
- Suggest alternatives if first choice unavailable

For APPOINTMENT INQUIRIES:
- Verify patient identity with name and DOB
- Show real appointment details from database
- Offer to help with changes if needed

For GENERAL QUESTIONS:
- Provide helpful guidance about our services
- Direct them toward the information they need
- Stay within your capabilities

🎯 RESPONSE STRATEGY:
Based on the intent '{intent}' and available information, your response should:
- Address their specific need
- Use any database results provided
- Ask for missing information naturally
- Guide them toward the next logical step
- Be warm, professional, and helpful

CRITICAL: Never generate specific appointment details, doctor schedules, or availability information unless it comes directly from database tool results."""
    
    # Include database tool results if available
    if last_tool_result:
        system_prompt += f"\n\n📋 LATEST DATABASE RESULT:\n{last_tool_result}\n\nUse this information to provide accurate, helpful responses."
    
    # Handle clarification needs
    if requires_clarification:
        system_prompt += f"\n\n⚠️ NEEDS CLARIFICATION: {', '.join(requires_clarification)}\nAddress these gaps in your response."
    
    try:
        # Get enhanced AI response with full context
        ai_response = get_ai_response(
            system_prompt, 
            state["current_message"],
            state.get("messages", [])[-10:],  # Last 10 messages for context
            db_context
        )
        
        state["ai_response"] = ai_response
        
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        state["ai_response"] = generate_fallback_response(state)
    
    return state

def build_comprehensive_context(state: HospitalState) -> str:
    """Build comprehensive context information for Claude"""
    context = ""
    
    # Database context
    db_context = state.get("db_context", {})
    if db_context:
        specializations = db_context.get("specializations", [])
        if specializations:
            context += f"Available Specializations: {', '.join([s.get('name', '') for s in specializations[:10]])}\n"
        
        doctors = db_context.get("doctors", [])
        if doctors:
            context += f"Active Doctors: {len(doctors)} across all specializations\n"
    
    # Tools used and results
    tools_used = state.get("tools_used", [])
    if tools_used:
        context += f"Database Tools Used: {', '.join(tools_used)}\n"
    
    # Patient status
    if state.get("patient_exists"):
        context += "Patient Status: Found in database\n"
    elif state.get("patient_name") and state.get("date_of_birth"):
        context += "Patient Status: New patient (not found in database)\n"
    
    # Conversation context
    conversation_context = state.get("conversation_context", {})
    if conversation_context:
        context += f"Conversation Context: {conversation_context}\n"
    
    return context if context else "No additional context available"

def generate_fallback_response(state: HospitalState) -> str:
    """Generate fallback response if AI generation fails"""
    intent = state.get("intent", "unclear")
    
    fallback_responses = {
        "book_appointment": "I'd be happy to help you book an appointment. To get started, I'll need your full name and date of birth. What's your name?",
        "inquiry": "I can help you check your appointments. Please provide your full name and date of birth so I can look up your records.",
        "availability_check": "I can check doctor availability for you. Which specialty or doctor would you like to see?",
        "reschedule": "I can help you reschedule your appointment. Please provide your name and date of birth so I can find your existing appointment.",
        "cancel": "I can help you cancel your appointment. Please provide your name and date of birth so I can locate your appointment.",
        "greeting": "Hello! I'm here to help you with appointment booking, checking your existing appointments, or finding doctor availability. How can I assist you today?"
    }
    
    return fallback_responses.get(intent, "I'm here to help with your medical appointments. How can I assist you today?")

    # Build messages for the LLM
    messages = [SystemMessage(content=system_prompt)]
    
    # Add chat history if available
    chat_history = state.get("messages", [])
    for msg in chat_history[-5:]:  # Last 5 messages for context
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg.get("content", "")))
    
    # Add current message
    messages.append(HumanMessage(content=state["current_message"]))
    
    # Create tools list
    tools = [query_doctor_availability, query_patient_appointments, book_appointment]
    
    # Create chain with tools
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.tools import tool
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    
    # Create chain with tools
    chain = prompt | llm.bind_tools(tools) | StrOutputParser()
    
    # Get response with tools
    try:
        response = chain.invoke({"input": state["current_message"]})
        state["ai_response"] = response
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        state["ai_response"] = "I'm having trouble processing your request. Please try again."
    
    return state

def attempt_booking(state: HospitalState) -> HospitalState:
    """Attempt to book appointment if conditions are met"""
    if not state.get("should_book", False):
        return state
    
    try:
        # Prepare booking parameters
        patient_name = state.get("patient_name", "")
        date_of_birth = state.get("date_of_birth", "")
        specialization = state.get("specialization", "General Medicine")
        doctor_preference = state.get("doctor_preference")
        preferred_date = state.get("preferred_date")
        preferred_time = state.get("preferred_time")
        
        # Call booking tool with positional arguments
        result = book_appointment(
            patient_name,
            date_of_birth,
            specialization,
            doctor_preference,
            preferred_date,
            preferred_time
        )
        
        state["ai_response"] = f"✅ {result}\n\nPlease arrive 15 minutes early for check-in. If you need to reschedule or cancel, please let me know!"
        state["tools_used"].append("book_appointment")
        
    except Exception as e:
        logger.error(f"Error in booking attempt: {e}")
        state["ai_response"] = f"⚠️ Booking failed: {str(e)}\n\nWould you like me to help you find alternative options?"
    
    return state

def update_messages(state: HospitalState) -> HospitalState:
    """Update conversation messages"""
    messages = state.get("messages", [])
    
    # Add user message
    messages.append({
        "role": "user",
        "content": state["current_message"],
        "timestamp": datetime.now().isoformat()
    })
    
    # Add AI response
    if state.get("ai_response"):
        messages.append({
            "role": "assistant",
            "content": state["ai_response"],
            "timestamp": datetime.now().isoformat()
        })
    
    # Keep only last 20 messages
    if len(messages) > 20:
        messages = messages[-20:]
    
    state["messages"] = messages
    return state

# ============================================================================
# LangGraph Workflow
# ============================================================================

def create_hospital_graph():
    """Create enhanced LangGraph for dynamic hospital conversation workflow"""
    
    if not LANGGRAPH_AVAILABLE:
        logger.warning("LangGraph not available, returning None")
        return None
    
    # Create the graph
    workflow = StateGraph(HospitalState)
    
    # Add enhanced workflow nodes
    workflow.add_node("extract_details", extract_appointment_details)
    workflow.add_node("determine_action", determine_next_action)
    workflow.add_node("validate_patient", validate_patient_data)
    workflow.add_node("execute_db_ops", execute_database_operations)
    workflow.add_node("check_booking", should_attempt_booking)
    workflow.add_node("generate_response", generate_ai_response)
    workflow.add_node("attempt_booking", attempt_booking)
    workflow.add_node("update_messages", update_messages)
    
    # Set entry point
    workflow.set_entry_point("extract_details")
    
    # Define conditional routing based on state
    def route_after_extract(state: HospitalState) -> str:
        """Route after extraction based on confidence and intent"""
        confidence = state.get("confidence_score", 0.0)
        intent = state.get("intent", "unclear")
        
        if confidence < 0.3 or intent == "unclear":
            return "generate_response"  # Go directly to response for low confidence
        else:
            return "determine_action"  # Continue with action determination
    
    def route_after_action(state: HospitalState) -> str:
        """Route after action determination"""
        needs_db_check = state.get("needs_database_check", False)
        patient_name = state.get("patient_name")
        date_of_birth = state.get("date_of_birth")
        
        if needs_db_check and patient_name and date_of_birth:
            return "validate_patient"
        elif needs_db_check:
            return "execute_db_ops"
        else:
            return "check_booking"
    
    def route_after_validation(state: HospitalState) -> str:
        """Route after patient validation"""
        needs_db_ops = state.get("needs_database_check", False)
        
        if needs_db_ops:
            return "execute_db_ops"
        else:
            return "check_booking"
    
    def route_after_db_ops(state: HospitalState) -> str:
        """Route after database operations"""
        return "check_booking"
    
    def route_after_booking_check(state: HospitalState) -> str:
        """Route after booking check"""
        should_book = state.get("should_book", False)
        
        if should_book:
            return "attempt_booking"
        else:
            return "generate_response"
    
    def route_after_response(state: HospitalState) -> str:
        """Route after response generation"""
        should_book = state.get("should_book", False)
        
        if should_book and not state.get("tools_used") or "book_appointment" not in state.get("tools_used", []):
            return "attempt_booking"
        else:
            return "update_messages"
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "extract_details",
        route_after_extract,
        {
            "determine_action": "determine_action",
            "generate_response": "generate_response"
        }
    )
    
    workflow.add_conditional_edges(
        "determine_action",
        route_after_action,
        {
            "validate_patient": "validate_patient",
            "execute_db_ops": "execute_db_ops",
            "check_booking": "check_booking"
        }
    )
    
    workflow.add_conditional_edges(
        "validate_patient",
        route_after_validation,
        {
            "execute_db_ops": "execute_db_ops",
            "check_booking": "check_booking"
        }
    )
    
    workflow.add_conditional_edges(
        "execute_db_ops",
        route_after_db_ops,
        {
            "check_booking": "check_booking"
        }
    )
    
    workflow.add_conditional_edges(
        "check_booking",
        route_after_booking_check,
        {
            "attempt_booking": "attempt_booking",
            "generate_response": "generate_response"
        }
    )
    
    workflow.add_conditional_edges(
        "generate_response",
        route_after_response,
        {
            "attempt_booking": "attempt_booking",
            "update_messages": "update_messages"
        }
    )
    
    # Final edge
    workflow.add_edge("attempt_booking", "update_messages")
    workflow.add_edge("update_messages", END)
    
    return workflow.compile()

# ============================================================================
# Conversation Manager with LangChain
# ============================================================================

class LangChainConversationManager:
    """Enhanced conversation manager using LangChain and LangGraph"""
    
    def __init__(self):
        self.graph = create_hospital_graph()
        self.memories = {}  # Session-based memories
        self.llm = get_llm()
        
        # Initialize RAG if available
        if RAG_AVAILABLE:
            self._initialize_rag()
        else:
            self.rag_index = None
            self.rag_documents = []
            self.embedding_model = None
            self.vector_store = None
            self.knowledge_base = []
        
        # Check if graph is available
        if self.graph is None:
            logger.warning("LangGraph not available, falling back to basic conversation")
    
    def _get_memory(self, session_id: str) -> HospitalMemory:
        """Get or create memory for session"""
        if session_id not in self.memories:
            self.memories[session_id] = HospitalMemory(session_id)
        return self.memories[session_id]
    
    def _get_redis_chat_history(self, session_id: str):
        """Get Redis chat history if available"""
        if REDIS_CHAT_HISTORY_AVAILABLE:
            try:
                # Build Redis URL with authentication if password is provided
                redis_url = REDIS_CONFIG['url']
                if REDIS_CONFIG.get('password'):
                    # Parse the URL and add password
                    if redis_url.startswith('redis://'):
                        redis_url = redis_url.replace('redis://', f'redis://:{REDIS_CONFIG["password"]}@')
                    elif redis_url.startswith('rediss://'):
                        redis_url = redis_url.replace('rediss://', f'rediss://:{REDIS_CONFIG["password"]}@')
                
                # Create Redis URL with database number if specified
                if REDIS_CONFIG.get('db', 0) != 0:
                    if '?' in redis_url:
                        redis_url += f"&db={REDIS_CONFIG.get('db', 0)}"
                    else:
                        redis_url += f"?db={REDIS_CONFIG.get('db', 0)}"
                
                return RedisChatMessageHistory(
                    session_id=session_id,
                    url=redis_url
                )
            except Exception as e:
                logger.warning(f"Redis chat history not available: {e}")
                return None
        return None
    
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
            # Get database context
            conn = get_db_connection()
            if not conn:
                return
            
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
                
                # Build knowledge entries
                knowledge_entries = []
                
                # Add doctor information
                for doctor in doctors:
                    entry = f"Dr. {doctor['name']} is a {doctor['specialization']} with {doctor.get('experience_years', 'several')} years of experience."
                    knowledge_entries.append(entry)
                
                # Add general hospital information
                knowledge_entries.extend([
                    "To book an appointment, we need patient name, phone number, date of birth, preferred doctor or specialty, and preferred date/time.",
                    "Our doctors are available Monday through Friday, with some weekend availability.",
                    "Appointment slots are typically 30-60 minutes depending on the specialty.",
                    "We require 24-hour notice for appointment cancellations.",
                    "New patients should arrive 30 minutes early for registration.",
                    "We accept most major insurance plans.",
                    "Emergency cases should call 911 or go to the nearest emergency room.",
                    "For urgent but non-emergency cases, we offer same-day appointments when available."
                ])
                
                self.knowledge_base = knowledge_entries
                
                # Create embeddings and vector store
                if knowledge_entries:
                    embeddings = self.embedding_model.encode(knowledge_entries)
                    dimension = embeddings.shape[1]
                    self.vector_store = faiss.IndexFlatL2(dimension)
                    self.vector_store.add(embeddings.astype('float32'))
                    logger.info(f"✅ Vector store built with {len(knowledge_entries)} entries")
                
        except Exception as e:
            logger.error(f"Error building knowledge base: {e}")
    
    def _get_relevant_context(self, query: str, top_k: int = 3) -> str:
        """Get relevant context using RAG"""
        if not RAG_AVAILABLE or self.vector_store is None:
            return ""
        
        try:
            query_embedding = self.embedding_model.encode([query])
            distances, indices = self.vector_store.search(query_embedding.astype('float32'), top_k)
            
            relevant_docs = []
            for idx in indices[0]:
                if idx < len(self.knowledge_base):
                    relevant_docs.append(self.knowledge_base[idx])
            
            return "\n".join(relevant_docs)
        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            return ""
    
    def process_message(self, user_message: str, session_id: str = None) -> Dict[str, Any]:
        """Process message using tools-based approach"""
        try:
            if not session_id:
                session_id = str(uuid.uuid4())
            
            logger.info(f"Processing message: {user_message[:50]}...")
            
            # Get Redis chat history if available
            redis_history = self._get_redis_chat_history(session_id)
            
            # Get memory for this session
            memory = self._get_memory(session_id)
            memory_vars = memory.load_memory_variables({})
            
            # Use tools-based approach
            logger.info("Using tools-based workflow")
            
            # Create tools list
            tools = [query_doctor_availability, query_patient_appointments, book_appointment]
            
            # Build system prompt
            system_prompt = """You are a warm, friendly AI healthcare assistant helping patients book appointments at our hospital. You have real-time access to our medical database and can make actual bookings.

CRITICAL: You MUST use the database tools to get real information. NEVER make up or hallucinate data.

AVAILABLE TOOLS:
- query_doctor_availability(specialty, target_date): Get real doctor availability by specialty
- query_patient_appointments(patient_name, date_of_birth): Check existing patient appointments
- book_appointment(patient_name, date_of_birth, specialization, doctor_preference, preferred_date, preferred_time): Actually book appointments

CORE BEHAVIOR PRINCIPLES:

💬 BE CONVERSATIONAL & NATURAL:
- Sound like a helpful receptionist, not a robot
- Use warm greetings: "Hello! How can I help you today?"
- Acknowledge what users say: "I understand", "Of course!", "Great!"
- Use contractions: "I'd", "you'll", "we're"
- Add transitions: "Perfect!", "Let me check that for you"

📝 DYNAMIC INFORMATION GATHERING:
- Don't ask for everything at once
- If someone says "I want to book an appointment", respond: "I'd be happy to help! May I have your name please?"
- Remember what they've told you - don't ask twice
- If they give multiple pieces of info, acknowledge all of them

📄 DATABASE INTEGRATION - CRITICAL:
- ALWAYS use query_doctor_availability() when asked about doctor availability
- ALWAYS use query_patient_appointments() when asked about patient appointments
- ALWAYS use book_appointment() when confirming a booking
- NEVER make up doctor names, availability, or appointment times
- NEVER hallucinate data - only use real database information

CONVERSATIONAL RESPONSES:

For availability queries:
- User: "What is the availability in cardiology?"
- You: "Let me check the real availability for cardiology doctors..." [USE query_doctor_availability("cardiology")]

For specific doctor queries:
- User: "When is Karen available?"
- You: "Let me check Dr. Karen Lee's real schedule..." [USE query_doctor_availability("cardiology") and filter for Karen]

For booking requests:
- User: "Book me an appointment"
- You: "I'll help you book that. Let me use the booking system..." [USE book_appointment() with provided details]

SMART BOOKING PROCESS:
1. Greet warmly and ask for their name
2. Thank them and ask for date of birth 
3. Ask what type of doctor or if they have someone specific in mind
4. Find out their preferred timing
5. Confirm all details conversationally
6. When they say "yes", use book_appointment() to actually book it

REMEMBER CONTEXT:
- If discussing Dr. Lisa (General Medicine), don't book Cardiology
- If they mentioned a specialty, stick with it
- Don't override their preferences with wrong specialties

CONVERSATION EXCELLENCE:

✅ DO:
- Start responses acknowledging what they said
- Use their name once you know it
- Be empathetic: "I understand that can be concerning"
- Provide clear next steps
- Remember conversation context
- ALWAYS use database tools for real information

❌ DON'T:
- Give robotic lists of information
- Say "No doctors found" - instead offer alternatives
- Ask for information they already provided
- Generate fake confirmations
- Switch specialties randomly
- Use technical error messages
- EVER make up or hallucinate data

Remember: Be conversational, helpful, and ALWAYS use real database information through the available tools. Never hallucinate doctor names, availability, or appointment times."""

            # Build messages
            messages = [SystemMessage(content=system_prompt)]
            
            # Add chat history if available
            chat_history = memory_vars.get("chat_history", [])
            for msg in chat_history[-5:]:  # Last 5 messages for context
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))
            
            # Add current message
            messages.append(HumanMessage(content=user_message))
            
            # Create chain with tools
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            
            # Create prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}")
            ])
            
            # Get response with tools
            try:
                # Check if the message is asking about availability
                if any(word in user_message.lower() for word in ['availability', 'available', 'schedule', 'cardiology', 'neurology', 'orthopedics', 'pediatrics', 'dermatology', 'psychiatry', 'gynecology']):
                    # Extract specialty from message
                    specialties = ['cardiology', 'neurology', 'orthopedics', 'pediatrics', 'dermatology', 'psychiatry', 'gynecology', 'general medicine']
                    specialty = None
                    for spec in specialties:
                        if spec in user_message.lower():
                            specialty = spec
                            break
                    
                    if specialty:
                        # Call the tool directly
                        tool_result = query_doctor_availability(specialty)
                        response = f"Let me check the real availability for {specialty} doctors...\n\n{tool_result}"
                    else:
                        response = self.llm.invoke(messages)
                        if hasattr(response, 'content'):
                            response = response.content
                        else:
                            response = str(response)
                else:
                    response = self.llm.invoke(messages)
                    if hasattr(response, 'content'):
                        response = response.content
                    else:
                        response = str(response)
                
                # Save to memory
                memory.save_context(
                    {"user_message": user_message},
                    {"ai_response": response}
                )
                
                # Save to Redis if available (non-critical)
                if redis_history:
                    try:
                        redis_history.add_user_message(user_message)
                        redis_history.add_ai_message(response)
                    except Exception as e:
                        # Redis is not critical, just log and continue
                        logger.debug(f"Redis save failed (non-critical): {e}")
                
                return {
                    'success': True,
                    'response': response,
                    'session_id': session_id,
                    'patient_name': memory_vars.get("patient_name"),
                    'booking_intent': "book" in user_message.lower() or "appointment" in user_message.lower(),
                    'tools_used': ["database_tools"],
                    'appointment_booked': 'book_appointment' in response.lower()
                }
                
            except Exception as e:
                logger.error(f"Error in tools-based workflow: {e}")
                return self._process_message_basic(user_message, session_id, memory, memory_vars, redis_history)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                'success': False,
                'response': "I apologize, but I encountered an error processing your request. Please try again.",
                'session_id': session_id,
                'error': str(e)
            }
    
    def _process_message_basic(self, user_message: str, session_id: str, memory, memory_vars, redis_history=None) -> Dict[str, Any]:
        """Basic message processing without LangGraph"""
        try:
            # Get relevant context if RAG is available
            context = ""
            if RAG_AVAILABLE and hasattr(self, 'knowledge_base') and self.knowledge_base:
                context = self._get_relevant_context(user_message)
            
            # Create system prompt
            system_prompt = f"""You are a warm, friendly AI healthcare assistant helping patients book appointments at our hospital. You have real-time access to our medical database and can make actual bookings.

{context}

Please be helpful, professional, and guide patients through the booking process. If they want to book an appointment, ask for their name, date of birth, preferred specialization, and preferred date/time."""
            
            # Create messages
            messages = [SystemMessage(content=system_prompt)]
            
            # Add conversation history from Redis if available
            if redis_history:
                try:
                    redis_messages = redis_history.messages
                    for msg in redis_messages[-5:]:  # Last 5 messages
                        if hasattr(msg, 'type') and msg.type == 'human':
                            messages.append(HumanMessage(content=msg.content))
                        elif hasattr(msg, 'type') and msg.type == 'ai':
                            messages.append(AIMessage(content=msg.content))
                except Exception as e:
                    logger.warning(f"Failed to load Redis history: {e}")
            else:
                # Fallback to memory
                chat_history = memory_vars.get("chat_history", [])
                for msg in chat_history[-5:]:  # Last 5 messages
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    else:
                        messages.append(AIMessage(content=msg["content"]))
            
            # Add current message
            messages.append(HumanMessage(content=user_message))
            
            # Get response from LLM
            if self.llm:
                response = self.llm.invoke(messages)
                ai_response = response.content if hasattr(response, 'content') else str(response)
            else:
                ai_response = "I'm here to help you book an appointment. Could you please provide your name and date of birth?"
            
            # Save to memory
            memory.save_context(
                {"messages": [{"role": "user", "content": user_message}, {"role": "assistant", "content": ai_response}]},
                {}
            )
            
            # Save to Redis if available
            if redis_history:
                try:
                    redis_history.add_user_message(user_message)
                    redis_history.add_ai_message(ai_response)
                except Exception as e:
                    logger.warning(f"Failed to save to Redis: {e}")
            
            return {
                'success': True,
                'response': ai_response,
                'session_id': session_id,
                'patient_name': memory_vars.get("patient_name"),
                'booking_intent': False,
                'tools_used': [],
                'appointment_booked': False
            }
            
        except Exception as e:
            logger.error(f"Error in basic message processing: {e}")
            return {
                'success': False,
                'response': "I apologize, but I encountered an error processing your request. Please try again.",
                'session_id': session_id,
                'error': str(e)
            }
    
    def get_upcoming_appointments(self, patient_name: str, date_of_birth: str) -> List[Dict]:
        """Get upcoming appointments for a patient"""
        try:
            result = query_patient_appointments(patient_name, date_of_birth)
            
            # Parse the result to extract appointment details
            appointments = []
            if "upcoming appointments" in result.lower():
                # This is a simplified parser - in practice, you'd want more robust parsing
                lines = result.split('\n')
                current_apt = {}
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('Appointment #'):
                        if current_apt:
                            appointments.append(current_apt)
                        current_apt = {'id': line.split('#')[1]}
                    elif line.startswith('- Date:'):
                        current_apt['appointment_date'] = line.replace('- Date:', '').strip()
                    elif line.startswith('- Time:'):
                        current_apt['appointment_time'] = line.replace('- Time:', '').strip()
                    elif line.startswith('- Doctor:'):
                        current_apt['doctor_name'] = line.replace('- Doctor:', '').strip()
                
                if current_apt:
                    appointments.append(current_apt)
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting appointments: {e}")
            return []

# ============================================================================
# Enhanced Database Functions
# ============================================================================

def get_database_context():
    """Get comprehensive database context for AI responses"""
    try:
        conn = get_db_connection()
        if not conn:
            return {}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            context = {}
            
            # Get doctors summary
            cursor.execute("""
                SELECT d.first_name, d.last_name, s.name as specialization, 
                       d.experience_years, d.consultation_fee
                FROM doctors d
                JOIN specializations s ON d.specialization_id = s.id
                WHERE d.is_active = TRUE
                ORDER BY s.name, d.last_name
            """)
            doctors = [dict(row) for row in cursor.fetchall()]
            context['doctors'] = serialize_datetime_objects(doctors)
            
            # Get specializations
            cursor.execute("""
                SELECT s.name, COUNT(d.id) as doctor_count
                FROM specializations s
                LEFT JOIN doctors d ON s.id = d.specialization_id AND d.is_active = TRUE
                WHERE s.is_active = TRUE
                GROUP BY s.name
                ORDER BY s.name
            """)
            specializations = [dict(row) for row in cursor.fetchall()]
            context['specializations'] = serialize_datetime_objects(specializations)
            
            # Get recent appointments for context
            cursor.execute("""
                SELECT a.appointment_date, a.appointment_time, a.status,
                       p.first_name || ' ' || p.last_name as patient_name,
                       d.first_name || ' ' || d.last_name as doctor_name,
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
            context['recent_appointments'] = serialize_datetime_objects(recent_appointments)
            
            return context
            
    except Exception as e:
        logger.error(f"Error getting database context: {e}")
        return {}

# ============================================================================
# Enhanced Response Generation with Context
# ============================================================================

def generate_contextual_response(state: HospitalState) -> HospitalState:
    """Generate response with database context and RAG"""
    llm = get_llm()
    if not llm:
        state["ai_response"] = "I'm having trouble processing your request. Please try again."
        return state
    
    # Get database context
    db_context = get_database_context()
    
    # Get RAG context if available
    conversation_manager = globals().get('conversation_manager')
    rag_context = ""
    if conversation_manager and hasattr(conversation_manager, '_get_relevant_context'):
        rag_context = conversation_manager._get_relevant_context(state["current_message"])
    
    # Build enhanced system prompt with context
    system_prompt = f"""You are a warm, friendly AI healthcare assistant helping patients at our hospital. You have access to real-time database information and should provide accurate, helpful responses.

AVAILABLE DOCTORS AND SPECIALIZATIONS:
{json.dumps(db_context.get('specializations', []), indent=2)}

CURRENT DOCTORS:
{json.dumps(db_context.get('doctors', []), indent=2)}

RELEVANT CONTEXT:
{rag_context}

CONVERSATION PRINCIPLES:
1. **Be Natural & Conversational**: Sound like a helpful receptionist, not a robot
2. **Use Real Data**: Reference actual doctors and specializations from the database
3. **Progressive Information Gathering**: Don't ask for everything at once
4. **Remember Context**: Keep track of what the user has told you
5. **Empathetic Communication**: Be understanding of health concerns

RESPONSE PATTERNS:

For Greetings:
"Hello! Welcome to our hospital. I'm here to help you with appointments and answer any questions. How can I assist you today?"

For Appointment Booking:
- Collect info naturally: "I'd be happy to help you book an appointment! May I have your name please?"
- Acknowledge: "Great, [Name]! Now I'll need your date of birth for our records."
- Confirm: "Perfect! Let me book you with Dr. [Name] for [Date] at [Time]. Does this work for you?"

For Doctor Inquiries:
- Use real data: Reference actual doctors from the database
- Be helpful: "We have excellent [specialty] doctors. Let me tell you about them..."

For Availability:
- Check real availability using database tools
- Offer alternatives if requested time isn't available

IMPORTANT: 
- Use actual doctor names and specializations from the database context
- Never make up appointments or confirmations
- When user confirms booking, use the booking tool to create real appointments
- Be conversational and remember what they've told you across messages"""

    # Build messages with conversation history
    messages = []
    
    # Add system message
    messages.append(SystemMessage(content=system_prompt))
    
    # Add conversation history
    for msg in state.get("messages", [])[-10:]:  # Last 10 messages for context
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    
    # Add current message
    messages.append(HumanMessage(content=state["current_message"]))
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages(messages)
    
    # Create chain
    chain = prompt | llm | StrOutputParser()
    
    # Get response
    try:
        response = chain.invoke({})
        state["ai_response"] = response
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        state["ai_response"] = "I'm having trouble processing your request right now. Please try again in a moment."
    
    return state

# ============================================================================
# Updated Graph with Enhanced Response Generation
# ============================================================================

def create_enhanced_hospital_graph():
    """Create enhanced LangGraph for hospital conversation workflow"""
    
    if not LANGGRAPH_AVAILABLE:
        logger.warning("LangGraph not available, returning None")
        return None
    
    # Create the graph
    workflow = StateGraph(HospitalState)
    
    # Add nodes
    workflow.add_node("extract_details", extract_appointment_details)
    workflow.add_node("check_booking", should_attempt_booking)
    workflow.add_node("generate_response", generate_contextual_response)  # Use enhanced version
    workflow.add_node("attempt_booking", attempt_booking)
    workflow.add_node("update_messages", update_messages)
    
    # Set entry point
    workflow.set_entry_point("extract_details")
    
    # Add edges
    workflow.add_edge("extract_details", "check_booking")
    workflow.add_edge("check_booking", "generate_response")
    workflow.add_edge("generate_response", "attempt_booking")
    workflow.add_edge("attempt_booking", "update_messages")
    workflow.add_edge("update_messages", END)
    
    return workflow.compile()

# ============================================================================
# Enhanced Conversation Manager
# ============================================================================

class EnhancedLangChainConversationManager(LangChainConversationManager):
    """Enhanced conversation manager with better context handling"""
    
    def __init__(self):
        super().__init__()
        self.graph = create_enhanced_hospital_graph()  # Use enhanced version
    
    def clear_session(self, session_id: str):
        """Clear session memory"""
        if session_id in self.memories:
            self.memories[session_id].clear()
    
    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """Get current session state"""
        if session_id not in self.memories:
            return {}
        
        memory = self.memories[session_id]
        return memory.load_memory_variables({})
    
    def update_session_state(self, session_id: str, **updates):
        """Update session state"""
        memory = self._get_memory(session_id)
        memory.save_context({}, updates)

# ============================================================================
# Flask Routes with LangChain Integration
# ============================================================================

# Initialize the enhanced conversation manager
conversation_manager = EnhancedLangChainConversationManager()

@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat endpoint with LangChain integration"""
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
        
        # Process message with LangChain system
        result = conversation_manager.process_message(user_message, session_id)
        
        return jsonify(result)

    except Exception as e:
        logger.error(f"Chat endpoint error from {request.remote_addr}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'An error occurred processing your request',
            'error': str(e)
        }), 500

@app.route('/api/session/<session_id>/state', methods=['GET'])
def get_session_state(session_id: str):
    """Get current session state"""
    try:
        state = conversation_manager.get_session_state(session_id)
        return jsonify({
            'success': True,
            'session_id': session_id,
            'state': state
        })
    except Exception as e:
        logger.error(f"Error getting session state: {e}")
        return jsonify({
            'success': False,
            'message': 'Error retrieving session state'
        }), 500

@app.route('/api/session/<session_id>/clear', methods=['POST'])
def clear_session(session_id: str):
    """Clear session memory"""
    try:
        conversation_manager.clear_session(session_id)
        return jsonify({
            'success': True,
            'message': 'Session cleared successfully'
        })
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        return jsonify({
            'success': False,
            'message': 'Error clearing session'
        }), 500

@app.route('/api/appointments', methods=['GET', 'POST', 'DELETE'])
def appointments():
    """Enhanced appointments endpoint"""
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
                           p.first_name || ' ' || p.last_name as patient_name,
                           p.phone as patient_phone, p.email as patient_email,
                           d.first_name || ' ' || d.last_name as doctor_name,
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
                
                cursor.execute(query, params)
                appointments_data = [dict(row) for row in cursor.fetchall()]
                
                # Serialize datetime objects
                serialized_appointments = serialize_datetime_objects(appointments_data)
                
                logger.info(f"Found {len(appointments_data)} appointments")
                return jsonify({
                    'success': True,
                    'appointments': serialized_appointments,
                    'total': len(appointments_data)
                })
                
        except Exception as e:
            logger.error(f"Error fetching appointments: {e}")
            return jsonify({
                'success': False,
                'message': 'Error fetching appointments',
                'error': str(e)
            }), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'Invalid request data'}), 400
            
            # Use the booking tool
            result = book_appointment(
                patient_name=data.get('patient_name', ''),
                date_of_birth=data.get('date_of_birth', ''),
                specialization=data.get('specialization', 'General Medicine'),
                doctor_preference=data.get('doctor_preference'),
                preferred_date=data.get('preferred_date'),
                preferred_time=data.get('preferred_time')
            )
            
            if "successfully" in result:
                return jsonify({
                    'success': True,
                    'message': result
                })
            else:
                return jsonify({
                    'success': False,
                    'message': result
                }), 400
                
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            return jsonify({
                'success': False,
                'message': 'Error creating appointment',
                'error': str(e)
            }), 500

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    """Get doctors with availability information"""
    try:
        specialty = request.args.get('specialty')
        
        if specialty:
            result = query_doctor_availability(specialty)
            return jsonify({
                'success': True,
                'doctors_info': result
            })
        else:
            # Get all doctors
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': 'Database connection error'}), 500
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT d.id, d.first_name, d.last_name, d.experience_years, 
                           d.consultation_fee, s.name as specialization
                    FROM doctors d
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE d.is_active = TRUE
                    ORDER BY s.name, d.last_name, d.first_name
                """)
                
                doctors = [dict(row) for row in cursor.fetchall()]
                return jsonify({
                    'success': True,
                    'doctors': serialize_datetime_objects(doctors)
                })
                
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        return jsonify({
            'success': False,
            'message': 'Error fetching doctors',
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint with system status"""
    # Check if LLM is available
    llm_available = conversation_manager.llm is not None and BEDROCK_AVAILABLE
    
    status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected' if get_db_connection() else 'disconnected',
        'ai_service': 'available' if llm_available else 'unavailable',
        'langchain': 'enabled' if conversation_manager.llm else 'disabled',
        'bedrock': 'available' if BEDROCK_AVAILABLE else 'unavailable',
        'rag': 'enabled' if RAG_AVAILABLE else 'disabled',
        'memory_sessions': len(conversation_manager.memories)
    }
    
    return jsonify(status)

# ============================================================================
# Error Handlers
# ============================================================================

class MalformedRequestMiddleware:
    """Middleware to handle malformed requests gracefully"""
    
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app
    
    def __call__(self, environ, start_response):
        try:
            return self.wsgi_app(environ, start_response)
        except UnicodeDecodeError:
            logger.warning(f"Malformed request from {environ.get('REMOTE_ADDR', 'unknown')}")
            response = json.dumps({
                'success': False,
                'message': 'Malformed request'
            }).encode('utf-8')
            
            headers = [
                ('Content-Type', 'application/json'),
                ('Content-Length', str(len(response)))
            ]
            
            start_response('400 Bad Request', headers)
            return [response]

# Apply middleware
app.wsgi_app = MalformedRequestMiddleware(app.wsgi_app)

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTP {e.code} error: {e.description}")
    return jsonify({
        'success': False,
        'message': e.description,
        'error_code': e.code
    }), e.code

@app.errorhandler(Exception)
def handle_general_exception(e):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({
        'success': False,
        'message': 'An unexpected error occurred',
        'error': str(e)
    }), 500

# ============================================================================
# Main Application Entry Point
# ============================================================================

if __name__ == '__main__':
    logger.info("🏥 Starting Doc-AI Hospital Management System with LangChain")
    logger.info("=" * 60)
    
    # System status
    logger.info(f"✅ Database integration: {'Enabled' if get_db_connection() else 'Disabled'}")
    logger.info(f"✅ LangChain integration: {'Enabled' if conversation_manager.llm else 'Disabled'}")
    logger.info(f"✅ AWS Bedrock: {'Available' if BEDROCK_AVAILABLE else 'Unavailable'}")
    logger.info(f"✅ RAG capabilities: {'Enabled' if RAG_AVAILABLE else 'Disabled'}")
    logger.info(f"✅ Claude Guidance: {'Available' if GUIDANCE_AVAILABLE else 'Unavailable'}")
    
    # Test database connection
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM doctors WHERE is_active = TRUE")
                doctor_count = cursor.fetchone()[0]
                logger.info(f"✅ Database: Connected ({doctor_count} active doctors)")
            conn.close()
        except Exception as e:
            logger.error(f"❌ Database test failed: {e}")
    else:
        logger.error("❌ Database: Connection failed")
    
    logger.info("=" * 60)
    logger.info("🚀 Server starting on http://localhost:8000")
    logger.info("📊 Health check: http://localhost:8000/api/health")
    logger.info("💬 Chat endpoint: http://localhost:8000/api/chat")
    logger.info("=" * 60)
    
    # Run the Flask application
    app.run(
        host='0.0.0.0',
        port=8000,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        threaded=True
    )