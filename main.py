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

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'hospital'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
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
                    return False, f"No available doctors found for {details.specialization}"
                
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
    """Fallback system prompt when claude_guidance is not available"""
    
    total_doctors = len(db_context.doctors)
    total_specializations = len(db_context.specializations)
    recent_appointments = len(db_context.recent_appointments)
    
    doctor_list = '\n'.join([f"• Dr. {d['name']} - {d['specialization']} ({d['experience_years']} years exp.)" for d in db_context.doctors[:10]])
    specializations_list = ', '.join([s['name'] for s in db_context.specializations])
    
    return f"""You are an intelligent AI assistant for a hospital appointment booking system. You have access to real-time database information and can help patients with appointments and medical inquiries.

IMPORTANT: You should NOT attempt to book appointments directly. The system will automatically handle appointment booking when patients provide their information. Your role is to:
1. Help patients provide their information (name, date of birth, doctor preference, etc.)
2. Answer questions about doctors, specializations, and hospital services
3. Guide patients through the booking process
4. Provide general medical information and hospital information

Current Database Context:
- We have {total_doctors} active doctors across {total_specializations} specializations
- Available specializations: {specializations_list}
- Recent appointments: {recent_appointments} in the last week

Our Medical Team:
{doctor_list}

Relevant Information:
{rag_context}

You can help with:
1. Finding doctors by specialty
2. Checking availability 
3. Guiding patients through appointment booking (collect: patient name, date of birth, preferred doctor/specialty, preferred time)
4. General medical information
5. Hospital information

When helping with appointments, always collect:
- Patient full name (first and last name)
- Date of birth (MM/DD/YYYY or DD/MM/YYYY format)
- Preferred doctor or specialty
- Preferred date and time

DO NOT attempt to book appointments yourself. The system will handle booking automatically when all required information is provided.

Be helpful, professional, and provide specific information when available."""

class EnhancedConversationManager:
    def __init__(self):
        self.conversations = {}
        self.vector_store = None
        self.embedding_model = None
        self.knowledge_base = []
        self.appointment_manager = EnhancedAppointmentManager()
        
        if RAG_AVAILABLE:
            self._initialize_rag()
    
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
        if not self.vector_store or not self.embedding_model:
            return ""
        
        try:
            query_embedding = self.embedding_model.encode([query])
            scores, indices = self.vector_store.search(query_embedding.astype('float32'), k=3)
            
            relevant_info = []
            for idx in indices[0]:
                if idx < len(self.knowledge_base):
                    relevant_info.append(self.knowledge_base[idx])
            
            return "\n".join(relevant_info)
            
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
        
        # Enhanced patient name extraction
        name_patterns = [
            r'(?:name is|i am|i\'m|my name is|this is)\s+([a-zA-Z\s]+?)(?:\s|,|$)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # Capital first letters
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two word names
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                if len(potential_name.split()) >= 2:  # First and last name
                    details.patient_name = potential_name
                    break
        
        # Enhanced date of birth extraction
        dob_patterns = [
            r'(?:birth|born|dob|date of birth).*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
            r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4})',
            r'(\d{1,2}th\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4})',
        ]
        
        for pattern in dob_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                dob_text = match.group(1)
                # Convert "5th feb 2004" to "02/05/2004"
                if 'th' in dob_text.lower() or any(month in dob_text.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                    try:
                        # Parse date like "5th feb 2004"
                        date_match = re.search(r'(\d{1,2})(?:th|st|nd|rd)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})', dob_text, re.IGNORECASE)
                        if date_match:
                            day = int(date_match.group(1))
                            month_name = date_match.group(2).lower()
                            year = int(date_match.group(3))
                            
                            month_map = {
                                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                            }
                            month = month_map[month_name]
                            details.date_of_birth = f"{month:02d}/{day:02d}/{year}"
                            break
                    except:
                        pass
                else:
                    details.date_of_birth = dob_text
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
                if len(doctor_name.split()) >= 2:  # First and last name
                    details.doctor_preference = doctor_name
                    break
        
        # Enhanced date extraction
        date_patterns = [
            r'(?:on|for)\s+(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(?:on|for)\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
            r'(next\s+\w+)',
            r'(june|july|august|september|october|november|december)\s+\d{1,2}',
            r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                details.preferred_date = match.group(1).strip()
                break
        
        # Enhanced time extraction
        time_patterns = [
            r'(\d{1,2}:\d{2}\s*(?:am|pm))',
            r'(\d{1,2}\s*(?:am|pm))',
            r'(morning|afternoon|evening)',
            r'(\d{1,2}:\d{2})',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                details.preferred_time = match.group(1).strip()
                break
        
        # Check if we have enough information to attempt booking
        if details.patient_name and details.date_of_birth and (details.specialization or details.doctor_preference):
            return details
        
        return None
    
    def process_message(self, user_message: str, session_id: str = None) -> Dict[str, Any]:
        """Process user message with enhanced appointment booking logic"""
        try:
            if not session_id:
                session_id = str(uuid.uuid4())
            
            conversation_history = self.conversations.get(session_id, [])
            
            # Enhanced booking intent detection
            booking_keywords = ['book', 'schedule', 'appointment', 'reserve', 'confirm', 'yes', 'okay', 'sure']
            is_booking_request = any(keyword in user_message.lower() for keyword in booking_keywords)
            
            # Check if this is a confirmation of appointment details
            is_confirmation = any(word in user_message.lower() for word in ['confirm', 'yes', 'okay', 'sure', 'book it', 'that works'])
            
            # Check if this is providing missing information
            is_providing_info = any(word in user_message.lower() for word in ['name is', 'i am', 'born', 'birth', 'dob', 'date of birth'])
            
            # Try to extract appointment details from current message and conversation history
            appointment_details = self.extract_appointment_details(user_message, conversation_history)
            
            # If we have appointment details and this is a booking request or confirmation
            if appointment_details and appointment_details.patient_name and appointment_details.date_of_birth and (is_booking_request or is_confirmation or is_providing_info):
                logger.info(f"Attempting to book appointment for {appointment_details.patient_name}")
                
                # Attempt to book appointment
                success, message = self.appointment_manager.book_appointment(appointment_details)
                
                if success:
                    response = f"✅ {message}\n\nPlease arrive 15 minutes early for check-in. If you need to reschedule or cancel, please let me know!"
                    self.add_message(session_id, user_message, response)
                    return {
                        'response': response,
                        'session_id': session_id,
                        'success': True,
                        'appointment_booked': True,
                        'appointment_id': message.split('#')[1].split()[0] if '#' in message else None
                    }
                else:
                    response = f"⚠️ {message}\n\nWould you like me to help you find alternative options or book a different time?"
                    self.add_message(session_id, user_message, response)
                    return {
                        'response': response,
                        'session_id': session_id,
                        'success': False,
                        'booking_attempted': True
                    }
            
            # If we have partial appointment details, ask for missing information
            elif appointment_details and (appointment_details.patient_name or appointment_details.date_of_birth or appointment_details.doctor_preference):
                missing_info = []
                if not appointment_details.patient_name:
                    missing_info.append("your full name")
                if not appointment_details.date_of_birth:
                    missing_info.append("your date of birth")
                if not appointment_details.specialization and not appointment_details.doctor_preference:
                    missing_info.append("which doctor or specialty you need")
                if not appointment_details.preferred_date:
                    missing_info.append("your preferred date")
                if not appointment_details.preferred_time:
                    missing_info.append("your preferred time")
                
                if missing_info:
                    response = f"I'd be happy to help book your appointment! I still need the following information:\n"
                    for i, info in enumerate(missing_info, 1):
                        response += f"{i}. {info.title()}\n"
                    response += "\nPlease provide these details so I can check availability and book your appointment."
                    
                    self.add_message(session_id, user_message, response)
                    return {
                        'response': response,
                        'session_id': session_id,
                        'success': True,
                        'needs_more_info': True
                    }
            
            # Check for appointment lookup requests
            lookup_keywords = ['my appointments', 'find my appointments', 'look up', 'search']
            is_lookup_request = any(keyword in user_message.lower() for keyword in lookup_keywords)
            
            if is_lookup_request:
                # Try to extract patient info for lookup
                patient_info = self.extract_appointment_details(user_message, conversation_history)
                if patient_info and patient_info.patient_name and patient_info.date_of_birth:
                    appointments = self.get_upcoming_appointments(patient_info.patient_name, patient_info.date_of_birth)
                    if appointments:
                        response = f"Here are your upcoming appointments:\n\n"
                        for apt in appointments[:5]:  # Show first 5 appointments
                            response += f"• {apt['appointment_date']} at {apt['appointment_time']} with Dr. {apt['doctor_name']} ({apt['specialization']})\n"
                        response += "\nWould you like to book a new appointment or reschedule any of these?"
                    else:
                        response = f"I couldn't find any upcoming appointments for {patient_info.patient_name}. Would you like to book a new appointment?"
                    
                    self.add_message(session_id, user_message, response)
                    return {
                        'response': response,
                        'session_id': session_id,
                        'success': True,
                        'appointments_found': len(appointments) if appointments else 0
                    }
            
            # Get database context for AI response
            db_context = self._get_database_context()
            
            # Get relevant context using RAG
            rag_context = self._get_relevant_context(user_message)
            
            # Use enhanced system prompt if available, otherwise use fallback
            if GUIDANCE_AVAILABLE:
                try:
                    system_prompt = get_enhanced_system_prompt(db_context, rag_context)
                    logger.debug("Using enhanced system prompt from claude_guidance")
                except Exception as e:
                    logger.error(f"Error using enhanced system prompt: {e}")
                    system_prompt = get_fallback_system_prompt(db_context, rag_context)
            else:
                system_prompt = get_fallback_system_prompt(db_context, rag_context)
            
            # Get AI response
            if BEDROCK_AVAILABLE:
                ai_response = get_ai_response(system_prompt, user_message, conversation_history)
            else:
                ai_response = self._generate_fallback_response(user_message, db_context)
            
            # Store conversation
            self.add_message(session_id, user_message, ai_response)
            
            return {
                'response': ai_response,
                'session_id': session_id,
                'success': True,
                'context_used': len(rag_context) > 0,
                'guidance_used': GUIDANCE_AVAILABLE
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

# API Routes
@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat endpoint with proper appointment booking"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request format'
            }), 400

        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')

        if not user_message:
            return jsonify({
                'success': False,
                'message': 'Message cannot be empty'
            }), 400

        # Process message with enhanced logic
        result = conversation_manager.process_message(user_message, session_id)
        
        return jsonify(result)

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
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

if __name__ == '__main__':
    logger.info("🏥 Starting Enhanced Doc-AI Hospital Management System")
    logger.info(f"✅ Database: {'Connected' if get_db_connection() else 'Not Connected'}")
    logger.info(f"✅ AI Service: {'AWS Bedrock' if BEDROCK_AVAILABLE else 'Fallback Mode'}")
    logger.info(f"✅ RAG System: {'Enabled' if RAG_AVAILABLE else 'Disabled'}")
    logger.info(f"✅ Claude Guidance System: {'Enabled' if GUIDANCE_AVAILABLE else 'Fallback Mode'}")
    logger.info("🚀 Server starting on http://localhost:8000")
    
    app.run(host='0.0.0.0', port=8000, debug=True)