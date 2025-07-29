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

def get_db_connection():
    """Get database connection with error handling"""
    try:
        return psycopg2.connect(**DB_CONFIG)
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

class EnhancedConversationManager:
    def __init__(self):
        self.conversations = {}
        self.vector_store = None
        self.embedding_model = None
        self.knowledge_base = []
        
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
                "Appointments can be scheduled Monday through Friday, with some doctors available on weekends.",
                "We offer services in Cardiology, Dermatology, Pediatrics, Orthopedics, and Neurology.",
                "All appointments need to be confirmed before they are finalized.",
                "Patients can reschedule or cancel appointments by contacting the hospital."
            ])
            
            if knowledge_entries and self.embedding_model:
                # Create embeddings
                embeddings = self.embedding_model.encode(knowledge_entries)
                
                # Build FAISS index
                dimension = embeddings.shape[1]
                self.vector_store = faiss.IndexFlatIP(dimension)
                self.vector_store.add(embeddings.astype('float32'))
                self.knowledge_base = knowledge_entries
                
                logger.info(f"✅ Knowledge base built with {len(knowledge_entries)} entries")
                
        except Exception as e:
            logger.error(f"Knowledge base building failed: {e}")
    
    def _get_relevant_context(self, query: str, k: int = 3) -> str:
        """Get relevant context using RAG"""
        if not self.vector_store or not self.embedding_model:
            return ""
        
        try:
            # Get query embedding
            query_embedding = self.embedding_model.encode([query])
            
            # Search for similar content
            scores, indices = self.vector_store.search(query_embedding.astype('float32'), k)
            
            # Build context from retrieved knowledge
            relevant_context = []
            for i, idx in enumerate(indices[0]):
                if scores[0][i] > 0.3:  # Similarity threshold
                    relevant_context.append(self.knowledge_base[idx])
            
            return "\n".join(relevant_context)
            
        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            return ""
    
    def _execute_query(self, query: str, params: tuple = None) -> Optional[List[Dict]]:
        """Execute database query with error handling"""
        conn = get_db_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if query.strip().upper().startswith('SELECT'):
                    return [dict(row) for row in cursor.fetchall()]
                else:
                    conn.commit()
                    return [{'success': True}]
        except Exception as e:
            logger.error(f"Database query error: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def _get_database_context(self) -> DatabaseContext:
        """Get current database context for AI"""
        try:
            # Get doctors with specializations
            doctors_query = """
            SELECT d.id, 
                   CONCAT(d.first_name, ' ', d.last_name) as name,
                   d.first_name, d.last_name, d.email, d.phone,
                   d.experience_years, d.consultation_fee,
                   s.name as specialization, s.description as specialization_description
            FROM doctors d 
            LEFT JOIN specializations s ON d.specialization_id = s.id 
            WHERE d.is_active = true
            ORDER BY d.first_name, d.last_name
            """
            doctors = self._execute_query(doctors_query) or []
            
            # Get departments
            departments_query = "SELECT id, name, description FROM departments WHERE is_active = true"
            departments = self._execute_query(departments_query) or []
            
            # Get specializations
            specializations_query = "SELECT id, name, description FROM specializations"
            specializations = self._execute_query(specializations_query) or []
            
            # Get recent appointments
            recent_appointments_query = """
            SELECT a.id, a.appointment_date, a.appointment_time, a.status,
                   CONCAT(p.first_name, ' ', p.last_name) as patient_name, 
                   CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                   s.name as specialization
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN specializations s ON d.specialization_id = s.id
            WHERE a.appointment_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
            LIMIT 20
            """
            recent_appointments = self._execute_query(recent_appointments_query) or []
            
            return DatabaseContext(
                doctors=doctors,
                departments=departments,
                specializations=specializations,
                recent_appointments=recent_appointments
            )
        except Exception as e:
            logger.error(f"Error getting database context: {e}")
            return DatabaseContext(doctors=[], departments=[], specializations=[], recent_appointments=[])
    
    def add_message(self, session_id: str, user_message: str, ai_response: str):
        """Add message to conversation history"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        self.conversations[session_id].append({
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'ai_response': ai_response
        })
        
        # Keep only last 50 messages per session
        if len(self.conversations[session_id]) > 50:
            self.conversations[session_id] = self.conversations[session_id][-50:]
    
    def get_conversation(self, session_id: str) -> List[Dict]:
        """Get conversation history"""
        return self.conversations.get(session_id, [])
    
    def extract_appointment_details(self, message: str, conversation_history: List[Dict]) -> Dict:
        """Extract appointment details from conversation"""
        details = {}
        
        # Look for patient name
        name_patterns = [
            r"(?:name is|i'm|i am|my name is|call me)\s+([a-zA-Z\s]+)",
            r"patient\s+(?:name\s+)?(?:is\s+)?([a-zA-Z\s]+)",
            r"book.*for\s+([a-zA-Z\s]+)",
            r"^([A-Z][a-z]+\s+[A-Z][a-z]+)(?:,|\s|$)"  # First Last name pattern
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip().title()
                # Filter out common words that aren't names
                if not any(word in potential_name.lower() for word in ['doctor', 'appointment', 'book', 'schedule', 'available']):
                    details['patient_name'] = potential_name
                    break
        
        # Look for date of birth
        dob_patterns = [
            r"(?:date of birth|dob|born).*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})",
            r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})",
            r"(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})"
        ]
        
        for pattern in dob_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                details['date_of_birth'] = match.group(1)
                break
        
        # Look for doctor preference
        doctor_patterns = [
            r"(?:with\s+)?(?:dr\.?\s+|doctor\s+)([a-zA-Z\s]+)",
            r"(?:book.*with|see)\s+([a-zA-Z\s]+)"
        ]
        
        for pattern in doctor_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                doctor_name = match.group(1).strip().title()
                if 'smith' in doctor_name.lower():
                    details['doctor_name'] = 'John Smith'
                    details['doctor_id'] = 1  # Dr. John Smith has ID 1
                break
        
        # Look for specialty preference
        specialty_patterns = [
            r"(cardiology|cardiologist|heart)",
            r"(neurology|neurologist|brain)",
            r"(orthopedics|orthopedic|bone|joint)",
            r"(dermatology|dermatologist|skin)",
            r"(pediatrics|pediatrician|child)"
        ]
        
        for pattern in specialty_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                specialty = match.group(1).lower()
                if 'cardio' in specialty:
                    details['specialty'] = 'Cardiology'
                    details['specialization_id'] = 1
                elif 'neuro' in specialty:
                    details['specialty'] = 'Neurology'
                    details['specialization_id'] = 5
                elif 'ortho' in specialty:
                    details['specialty'] = 'Orthopedics'
                    details['specialization_id'] = 4
                elif 'derma' in specialty:
                    details['specialty'] = 'Dermatology'
                    details['specialization_id'] = 2
                elif 'pediatr' in specialty:
                    details['specialty'] = 'Pediatrics'
                    details['specialization_id'] = 3
                break
        
        # Look for day preference
        day_patterns = [
            r"(?:on\s+)?(?:this\s+|next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"(?:prefer|like)\s+.*?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        ]
        
        for pattern in day_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                details['preferred_day'] = match.group(1).lower()
                break
        
        # Look for time preference
        time_patterns = [
            r"(?:at\s+)?(\d{1,2}:?\d{0,2}\s*(?:am|pm|AM|PM))",
            r"(morning|afternoon|evening)"
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                details['preferred_time'] = match.group(1) if ':' in match.group(1) else match.group(0)
                break
        
        # Look through conversation history for missing details
        for msg in conversation_history[-5:]:  # Check last 5 messages
            user_msg = msg.get('user_message', '').lower()
            
            if 'patient_name' not in details:
                for pattern in name_patterns:
                    match = re.search(pattern, user_msg, re.IGNORECASE)
                    if match:
                        potential_name = match.group(1).strip().title()
                        if not any(word in potential_name.lower() for word in ['doctor', 'appointment', 'book', 'schedule', 'available']):
                            details['patient_name'] = potential_name
                            break
            
            if 'date_of_birth' not in details:
                for pattern in dob_patterns:
                    match = re.search(pattern, user_msg, re.IGNORECASE)
                    if match:
                        details['date_of_birth'] = match.group(1)
                        break
        
        return details
    
    def book_appointment(self, details: Dict) -> Tuple[bool, str]:
        """Book an appointment in the database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False, "Database connection failed"
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # First, check if patient exists or create new patient
                patient_id = None
                
                if details.get('patient_name'):
                    # Split name into first and last
                    name_parts = details['patient_name'].strip().split()
                    if len(name_parts) >= 2:
                        first_name = name_parts[0]
                        last_name = ' '.join(name_parts[1:])
                    else:
                        first_name = name_parts[0]
                        last_name = ''
                    
                    # Check if patient exists
                    cursor.execute(
                        "SELECT id FROM patients WHERE LOWER(first_name) = LOWER(%s) AND LOWER(last_name) = LOWER(%s) LIMIT 1",
                        (first_name, last_name)
                    )
                    existing_patient = cursor.fetchone()
                    
                    if existing_patient:
                        patient_id = existing_patient['id']
                    else:
                        # Create new patient
                        default_phone = f"+1-555-{str(hash(details['patient_name']))[-4:]}"
                        cursor.execute("""
                            INSERT INTO patients (first_name, last_name, phone, email, date_of_birth, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """, (
                            first_name,
                            last_name,
                            details.get('phone', default_phone),
                            details.get('email', f"{first_name.lower()}.{last_name.lower()}@example.com"),
                            details.get('date_of_birth'),
                            datetime.now()
                        ))
                        patient_id = cursor.fetchone()['id']
                
                if not patient_id:
                    return False, "Could not create or find patient record"
                
                # Get doctor ID
                doctor_id = details.get('doctor_id')
                if not doctor_id:
                    if details.get('specialty') or details.get('specialization_id'):
                        # Find doctor by specialty
                        spec_id = details.get('specialization_id')
                        if spec_id:
                            cursor.execute(
                                "SELECT id FROM doctors WHERE specialization_id = %s AND is_active = true LIMIT 1",
                                (spec_id,)
                            )
                        else:
                            cursor.execute("""
                                SELECT d.id FROM doctors d
                                JOIN specializations s ON d.specialization_id = s.id
                                WHERE s.name ILIKE %s AND d.is_active = true 
                                LIMIT 1
                            """, (f"%{details['specialty']}%",))
                        
                        doctor = cursor.fetchone()
                        if doctor:
                            doctor_id = doctor['id']
                    
                    if not doctor_id:
                        # Default to first available doctor
                        cursor.execute("SELECT id FROM doctors WHERE is_active = true LIMIT 1")
                        doctor = cursor.fetchone()
                        if doctor:
                            doctor_id = doctor['id']
                
                # Determine appointment date
                appointment_date = None
                if details.get('preferred_day'):
                    # Convert day name to date
                    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                    today = date.today()
                    today_weekday = today.weekday()
                    target_weekday = days.index(details['preferred_day'].lower())
                    
                    days_ahead = target_weekday - today_weekday
                    if days_ahead <= 0:  # Target day already passed this week
                        days_ahead += 7
                    
                    appointment_date = today + timedelta(days=days_ahead)
                else:
                    # Default to tomorrow
                    appointment_date = date.today() + timedelta(days=1)
                
                # Set appointment time
                appointment_time = time(9, 0)  # Default to 9:00 AM
                if details.get('preferred_time'):
                    try:
                        time_str = details['preferred_time'].upper().replace(' ', '')
                        if 'AM' in time_str or 'PM' in time_str:
                            time_part = time_str.replace('AM', '').replace('PM', '')
                            if ':' in time_part:
                                hour, minute = time_part.split(':')
                                hour = int(hour)
                                minute = int(minute)
                            else:
                                hour = int(time_part)
                                minute = 0
                            
                            if 'PM' in time_str and hour != 12:
                                hour += 12
                            elif 'AM' in time_str and hour == 12:
                                hour = 0
                            
                            appointment_time = time(hour, minute)
                        elif 'morning' in details['preferred_time'].lower():
                            appointment_time = time(9, 0)
                        elif 'afternoon' in details['preferred_time'].lower():
                            appointment_time = time(14, 0)
                        elif 'evening' in details['preferred_time'].lower():
                            appointment_time = time(17, 0)
                    except:
                        pass  # Keep default time if parsing fails
                
                # Create appointment
                cursor.execute("""
                    INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, 
                                            status, reason_for_visit, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    patient_id,
                    doctor_id,
                    appointment_date,
                    appointment_time,
                    'scheduled',
                    'Consultation',
                    datetime.now()
                ))
                
                appointment_id = cursor.fetchone()['id']
                conn.commit()
                
                return True, f"Appointment booked successfully! Appointment ID: {appointment_id}"
                
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            if conn:
                conn.rollback()
            return False, f"Failed to book appointment: {str(e)}"
        finally:
            if conn:
                conn.close()
    
    def process_message(self, user_message: str, session_id: str) -> Dict:
        """Process user message with appointment booking capability"""
        try:
            if not user_message.strip():
                return {
                    'response': "Could you please ask me something?",
                    'session_id': session_id,
                    'success': True
                }
            
            user_message = user_message.strip()
            
            # Get conversation history
            conversation_history = self.get_conversation(session_id)
            
            # Check if this looks like an appointment booking request
            booking_keywords = ['book', 'appointment', 'schedule', 'reserve', 'see doctor', 'visit']
            is_booking_request = any(keyword in user_message.lower() for keyword in booking_keywords)
            
            # Check if we have enough details to book
            if is_booking_request or any('book' in msg.get('user_message', '').lower() for msg in conversation_history[-3:]):
                appointment_details = self.extract_appointment_details(user_message, conversation_history)
                
                # If we have minimum required details, attempt booking
                if appointment_details.get('patient_name') and appointment_details.get('date_of_birth'):
                    success, booking_message = self.book_appointment(appointment_details)
                    
                    if success:
                        response = f"Great! I've successfully booked your appointment. {booking_message}\n\nPlease arrive 15 minutes early to complete any necessary paperwork. If you need to reschedule or have any questions, feel free to ask!"
                        self.add_message(session_id, user_message, response)
                        return {
                            'response': response,
                            'session_id': session_id,
                            'success': True,
                            'appointment_booked': True
                        }
                    else:
                        response = f"I encountered an issue while booking your appointment: {booking_message}. Please try again or contact our support team."
                        self.add_message(session_id, user_message, response)
                        return {
                            'response': response,
                            'session_id': session_id,
                            'success': False
                        }
            
            # Get database context
            db_context = self._get_database_context()
            
            # Get relevant context using RAG
            rag_context = self._get_relevant_context(user_message)
            
            # Build enhanced system prompt
            system_prompt = f"""You are a helpful AI assistant for a hospital appointment booking system.

Current Database Context:
- We have {len(db_context.doctors)} active doctors
- Available specializations: {', '.join([s['name'] for s in db_context.specializations])}
- Recent appointments: {len(db_context.recent_appointments)} in the last week

Our Doctors:
{chr(10).join([f"- Dr. {d['name']} ({d['specialization']}) - {d['experience_years']} years experience" for d in db_context.doctors])}

Relevant Information:
{rag_context}

You can help with:
1. Finding doctors by specialty
2. Checking availability 
3. Booking appointments (collect: patient name, date of birth, preferred doctor/specialty, preferred time)
4. General medical information
5. Hospital information

When booking appointments, always collect:
- Patient full name (first and last name)
- Date of birth (MM/DD/YYYY or DD/MM/YYYY format)
- Preferred doctor or specialty
- Preferred date/time

Be helpful, professional, and provide specific information when available."""

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
                'context_used': len(rag_context) > 0
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                'response': "I apologize, but I'm experiencing technical difficulties. Please try again.",
                'session_id': session_id,
                'success': False,
                'error': str(e)
            }
    
    def _generate_fallback_response(self, user_message: str, db_context: DatabaseContext) -> str:
        """Enhanced fallback response system using database context"""
        
        user_lower = user_message.lower()
        
        # Doctor inquiry
        if any(word in user_lower for word in ['doctor', 'doctors', 'available', 'specialist']):
            if 'cardiologist' in user_lower or 'heart' in user_lower:
                cardiologists = [d for d in db_context.doctors if 'cardio' in d['specialization'].lower()]
                if cardiologists:
                    doc_list = ', '.join([f"Dr. {d['name']}" for d in cardiologists])
                    return f"We have the following cardiologists available: {doc_list}. Would you like to book an appointment with any of them?"
                else:
                    return "I don't see any cardiologists in our current roster. Let me check our full doctor list for you."
            else:
                doc_list = ', '.join([f"Dr. {d['name']} ({d['specialization']})" for d in db_context.doctors[:5]])
                return f"Here are some of our available doctors: {doc_list}. What type of doctor do you need to see?"
        
        # Booking inquiry
        elif any(word in user_lower for word in ['book', 'appointment', 'schedule']):
            return "I'd be happy to help you book an appointment! To get started, I'll need:\n1. Your full name\n2. Your date of birth\n3. Which doctor or specialty you'd like to see\n4. Your preferred date and time\n\nPlease provide these details and I'll book your appointment."
        
        # Availability inquiry
        elif any(word in user_lower for word in ['available', 'availability', 'free', 'open']):
            return f"We have doctors available across {len(db_context.specializations)} specializations: {', '.join([s['name'] for s in db_context.specializations])}. What specialty are you interested in?"
        
        # Default response with context
        else:
            return f"Hello! I'm your AI healthcare assistant. I can help you book appointments with our {len(db_context.doctors)} doctors, find specialists, or answer health questions. How can I assist you today?"

# Initialize the conversation manager
conversation_manager = EnhancedConversationManager()

def execute_sql_query(query: str, params: tuple = None) -> Optional[List[Dict]]:
    """Execute SQL query with proper error handling"""
    return conversation_manager._execute_query(query, params)

# API Routes
@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat endpoint with RAG capabilities"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'response': 'Invalid request format',
                'success': False
            }), 400
        
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        if not user_message:
            return jsonify({
                'response': 'Please provide a message',
                'session_id': session_id,
                'success': False
            }), 400
        
        # Process message
        result = conversation_manager.process_message(user_message, session_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return jsonify({
            'response': 'An error occurred processing your request',
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/appointments', methods=['GET'])
def get_appointments():
    """Get all appointments"""
    try:
        query = """
        SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.reason_for_visit,
               CONCAT(p.first_name, ' ', p.last_name) as patient_name, 
               p.phone as patient_phone,
               CONCAT(d.first_name, ' ', d.last_name) as doctor_name, 
               s.name as specialization
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN specializations s ON d.specialization_id = s.id
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 50
        """
        
        appointments = execute_sql_query(query)
        
        if appointments is None:
            return jsonify([])
        
        # Format appointments for frontend
        formatted_appointments = []
        for apt in appointments:
            formatted_appointments.append({
                'id': apt['id'],
                'date': apt['appointment_date'].isoformat() if apt['appointment_date'] else None,
                'time': str(apt['appointment_time']) if apt['appointment_time'] else None,
                'appointment_date': apt['appointment_date'].isoformat() if apt['appointment_date'] else None,
                'appointment_time': str(apt['appointment_time']) if apt['appointment_time'] else 'Time TBD',
                'status': apt['status'] or 'scheduled',
                'reason': apt['reason_for_visit'],
                'patient_name': apt['patient_name'],
                'patient_phone': apt['patient_phone'],
                'doctor_name': apt['doctor_name'],
                'specialization': apt['specialization'],
                'department': apt['specialization']  # Using specialization as department
            })
        
        return jsonify(formatted_appointments)
        
    except Exception as e:
        logger.error(f"Error fetching appointments: {e}")
        return jsonify([])

@app.route('/api/appointments', methods=['POST'])
def create_appointment():
    """Create a new appointment"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request format'
            }), 400
        
        # Extract required fields
        patient_name = data.get('patient_name', '').strip()
        doctor_id = data.get('doctor_id')
        appointment_date = data.get('appointment_date')
        appointment_time = data.get('appointment_time')
        reason = data.get('reason', 'Consultation')
        
        # Validate required fields
        if not all([patient_name, doctor_id, appointment_date, appointment_time]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: patient_name, doctor_id, appointment_date, appointment_time'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            }), 500
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Parse patient name
                name_parts = patient_name.strip().split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])
                else:
                    first_name = name_parts[0]
                    last_name = ''
                
                # Check if patient exists, create if not
                cursor.execute(
                    "SELECT id FROM patients WHERE LOWER(first_name) = LOWER(%s) AND LOWER(last_name) = LOWER(%s) LIMIT 1",
                    (first_name, last_name)
                )
                existing_patient = cursor.fetchone()
                
                if existing_patient:
                    patient_id = existing_patient['id']
                else:
                    # Create new patient
                    default_phone = f"+1-555-{str(hash(patient_name))[-4:]}"
                    cursor.execute("""
                        INSERT INTO patients (first_name, last_name, phone, email, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        first_name,
                        last_name,
                        data.get('phone', default_phone),
                        data.get('email', f"{first_name.lower()}.{last_name.lower()}@example.com"),
                        datetime.now()
                    ))
                    patient_id = cursor.fetchone()['id']
                
                # Validate doctor exists
                cursor.execute(
                    "SELECT id FROM doctors WHERE id = %s AND is_active = true",
                    (doctor_id,)
                )
                if not cursor.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Invalid doctor ID'
                    }), 400
                
                # Check for time conflicts
                cursor.execute("""
                    SELECT id FROM appointments 
                    WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s
                    AND status NOT IN ('cancelled')
                """, (doctor_id, appointment_date, appointment_time))
                
                if cursor.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Time slot already booked'
                    }), 409
                
                # Create appointment
                cursor.execute("""
                    INSERT INTO appointments (patient_id, doctor_id, appointment_date, 
                                            appointment_time, status, reason_for_visit, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    patient_id,
                    doctor_id,
                    appointment_date,
                    appointment_time,
                    'scheduled',
                    reason,
                    datetime.now()
                ))
                
                appointment_id = cursor.fetchone()['id']
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Appointment created successfully',
                    'appointment_id': appointment_id
                })
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating appointment: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to create appointment: {str(e)}'
            }), 500
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Create appointment endpoint error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred processing your request'
        }), 500

@app.route('/api/appointments/<int:appointment_id>', methods=['DELETE'])
def cancel_appointment(appointment_id):
    """Cancel an appointment"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            }), 500
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if appointment exists
                cursor.execute(
                    "SELECT id FROM appointments WHERE id = %s",
                    (appointment_id,)
                )
                if not cursor.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Appointment not found'
                    }), 404
                
                # Update appointment status to cancelled
                cursor.execute("""
                    UPDATE appointments 
                    SET status = 'cancelled', updated_at = %s
                    WHERE id = %s
                """, (datetime.now(), appointment_id))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Appointment cancelled successfully'
                })
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error cancelling appointment: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to cancel appointment: {str(e)}'
            }), 500
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Cancel appointment endpoint error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred processing your request'
        }), 500

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    """Get all doctors with availability info"""
    try:
        specialty = request.args.get('specialty')
        
        query = """
        SELECT d.id, 
               CONCAT(d.first_name, ' ', d.last_name) as name,
               d.first_name, d.last_name, d.email, d.phone,
               d.experience_years, d.consultation_fee,
               s.name as specialization, s.description as specialization_description
        FROM doctors d 
        LEFT JOIN specializations s ON d.specialization_id = s.id 
        WHERE d.is_active = true
        """
        params = ()
        
        if specialty:
            query += " AND LOWER(s.name) LIKE LOWER(%s)"
            params = (f"%{specialty}%",)
        
        query += " ORDER BY d.first_name, d.last_name"
        
        doctors = execute_sql_query(query, params)
        
        if doctors is None:
            return jsonify([])
        
        # Format doctors for frontend
        formatted_doctors = []
        for doctor in doctors:
            formatted_doctors.append({
                'id': doctor['id'],
                'name': doctor['name'],
                'first_name': doctor['first_name'],
                'last_name': doctor['last_name'],
                'specialization': doctor['specialization'],
                'department': doctor['specialization'],
                'phone': doctor['phone'],
                'email': doctor['email'],
                'experience_years': doctor['experience_years'],
                'consultation_fee': float(doctor['consultation_fee']) if doctor['consultation_fee'] else None
            })
        
        return jsonify(formatted_doctors)
        
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        return jsonify([])

@app.route('/api/departments', methods=['GET'])
def get_departments():
    """Get all departments with doctor counts"""
    try:
        query = """
        SELECT d.id, d.name, d.description,
               COUNT(doc.id) as doctor_count
        FROM departments d
        LEFT JOIN specializations s ON d.name = s.name
        LEFT JOIN doctors doc ON s.id = doc.specialization_id AND doc.is_active = true
        WHERE d.is_active = true
        GROUP BY d.id, d.name, d.description
        ORDER BY d.name
        """
        
        departments = execute_sql_query(query)
        
        if departments is None:
            return jsonify([])
        
        return jsonify([dict(dept) for dept in departments])
        
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return jsonify([])

@app.route('/api/specializations', methods=['GET'])
def get_specializations():
    """Get all specializations with doctor counts"""
    try:
        query = """
        SELECT s.id, s.name, s.description,
               COUNT(d.id) as doctor_count
        FROM specializations s
        LEFT JOIN doctors d ON s.id = d.specialization_id AND d.is_active = true
        GROUP BY s.id, s.name, s.description
        ORDER BY s.name
        """
        
        specializations = execute_sql_query(query)
        
        if specializations is None:
            return jsonify([])
        
        return jsonify([dict(spec) for spec in specializations])
        
    except Exception as e:
        logger.error(f"Error fetching specializations: {e}")
        return jsonify([])

@app.route('/api/patients', methods=['GET'])
def get_patients():
    """Get all patients"""
    try:
        query = """
        SELECT id, first_name, last_name, phone, email, date_of_birth, gender, created_at,
               CONCAT(first_name, ' ', last_name) as name
        FROM patients
        WHERE is_active = true
        ORDER BY first_name, last_name
        """
        
        patients = execute_sql_query(query)
        
        if patients is None:
            return jsonify([])
        
        # Format patients for frontend
        formatted_patients = []
        for patient in patients:
            formatted_patients.append({
                'id': patient['id'],
                'name': patient['name'],
                'first_name': patient['first_name'],
                'last_name': patient['last_name'],
                'phone': patient['phone'],
                'email': patient['email'],
                'date_of_birth': patient['date_of_birth'].isoformat() if patient['date_of_birth'] else None,
                'gender': patient['gender'],
                'created_at': patient['created_at'].isoformat() if patient['created_at'] else None
            })
        
        return jsonify(formatted_patients)
        
    except Exception as e:
        logger.error(f"Error fetching patients: {e}")
        return jsonify([])

@app.route('/api/patients', methods=['POST'])
def create_patient():
    """Register a new patient"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request format'
            }), 400
        
        # Extract required fields
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        phone = data.get('phone', '').strip()
        
        if not all([first_name, last_name, phone]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields: first_name, last_name, phone'
            }), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            }), 500
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if patient already exists
                cursor.execute(
                    "SELECT id FROM patients WHERE phone = %s",
                    (phone,)
                )
                if cursor.fetchone():
                    return jsonify({
                        'success': False,
                        'message': 'Patient with this phone number already exists'
                    }), 409
                
                # Create new patient
                cursor.execute("""
                    INSERT INTO patients (first_name, last_name, phone, email, 
                                        date_of_birth, gender, address, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    first_name,
                    last_name,
                    phone,
                    data.get('email'),
                    data.get('date_of_birth'),
                    data.get('gender'),
                    data.get('address'),
                    datetime.now()
                ))
                
                patient_id = cursor.fetchone()['id']
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Patient registered successfully',
                    'patient_id': patient_id
                })
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating patient: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to register patient: {str(e)}'
            }), 500
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Create patient endpoint error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred processing your request'
        }), 500

@app.route('/api/doctor_schedule', methods=['GET'])
def get_doctor_schedule():
    """Get doctor availability schedules"""
    try:
        doctor_id = request.args.get('doctor_id')
        date_param = request.args.get('date')
        
        query = """
        SELECT ds.id, ds.doctor_id, ds.date, ds.start_time, ds.end_time, ds.is_available,
               CONCAT(d.first_name, ' ', d.last_name) as doctor_name, 
               s.name as specialization
        FROM doctor_schedules ds
        JOIN doctors d ON ds.doctor_id = d.id
        JOIN specializations s ON d.specialization_id = s.id
        WHERE d.is_active = true
        """
        params = []
        
        if doctor_id:
            query += " AND ds.doctor_id = %s"
            params.append(doctor_id)
        
        if date_param:
            query += " AND ds.date = %s"
            params.append(date_param)
        else:
            # Default to next 7 days
            query += " AND ds.date >= CURRENT_DATE AND ds.date <= CURRENT_DATE + INTERVAL '7 days'"
        
        query += " ORDER BY ds.date, ds.start_time"
        
        schedules = execute_sql_query(query, tuple(params) if params else None)
        
        if schedules is None:
            return jsonify([])
        
        # Format schedules for frontend
        formatted_schedules = []
        for schedule in schedules:
            formatted_schedules.append({
                'id': schedule['id'],
                'doctor_id': schedule['doctor_id'],
                'doctor_name': schedule['doctor_name'],
                'specialization': schedule['specialization'],
                'date': schedule['date'].isoformat() if schedule['date'] else None,
                'start_time': str(schedule['start_time']) if schedule['start_time'] else None,
                'end_time': str(schedule['end_time']) if schedule['end_time'] else None,
                'is_available': schedule['is_available']
            })
        
        return jsonify(formatted_schedules)
        
    except Exception as e:
        logger.error(f"Error fetching doctor schedules: {e}")
        return jsonify([])

@app.route('/api/admin/appointments', methods=['GET'])
def get_admin_appointments():
    """Get all appointments with full details for admin"""
    try:
        query = """
        SELECT a.id, a.appointment_date, a.appointment_time, a.status, 
               a.reason_for_visit, a.notes, a.created_at,
               CONCAT(p.first_name, ' ', p.last_name) as patient_name, 
               p.phone as patient_phone, p.email as patient_email,
               CONCAT(d.first_name, ' ', d.last_name) as doctor_name, 
               s.name as specialization, d.phone as doctor_phone
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN specializations s ON d.specialization_id = s.id
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        """
        
        appointments = execute_sql_query(query)
        
        if appointments is None:
            return jsonify([])
        
        # Format appointments for admin view
        formatted_appointments = []
        for apt in appointments:
            formatted_appointments.append({
                'id': apt['id'],
                'appointment_date': apt['appointment_date'].isoformat() if apt['appointment_date'] else None,
                'appointment_time': str(apt['appointment_time']) if apt['appointment_time'] else None,
                'status': apt['status'],
                'reason': apt['reason_for_visit'],
                'notes': apt['notes'],
                'created_at': apt['created_at'].isoformat() if apt['created_at'] else None,
                'patient': {
                    'name': apt['patient_name'],
                    'phone': apt['patient_phone'],
                    'email': apt['patient_email']
                },
                'doctor': {
                    'name': apt['doctor_name'],
                    'specialization': apt['specialization'],
                    'phone': apt['doctor_phone']
                }
            })
        
        return jsonify(formatted_appointments)
        
    except Exception as e:
        logger.error(f"Error fetching admin appointments: {e}")
        return jsonify([])

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
            'vector_store': 'initialized' if conversation_manager.vector_store else 'not_available'
        })
        
    except Exception as e:
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
    logger.info("🏥 Starting Doc-AI Hospital Management System")
    logger.info(f"✅ Database: {'Connected' if get_db_connection() else 'Not Connected'}")
    logger.info(f"✅ AI Service: {'AWS Bedrock' if BEDROCK_AVAILABLE else 'Fallback Mode'}")
    logger.info(f"✅ RAG System: {'Enabled' if RAG_AVAILABLE else 'Disabled'}")
    logger.info("🚀 Server starting on http://localhost:8000")
    
    app.run(host='0.0.0.0', port=8000, debug=True)