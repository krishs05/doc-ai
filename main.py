# Enhanced main.py - Replace your existing main.py with this content
# This implements RAG-enhanced AI while keeping your existing file structure

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import uuid
from datetime import datetime, timedelta
import re
import os
import logging
from dotenv import load_dotenv
from typing import Dict, List, Optional
from dataclasses import dataclass

# Enhanced imports for RAG implementation
import numpy as np
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    RAG_AVAILABLE = True
except ImportError:
    print("⚠️  RAG libraries not installed. Install with: pip install sentence-transformers faiss-cpu")
    RAG_AVAILABLE = False

# Import existing bedrock functionality
try:
    from bedrock import get_ai_response, get_bedrock_client
    BEDROCK_AVAILABLE = True
except ImportError:
    print("⚠️  bedrock.py not found. AI features will be limited.")
    BEDROCK_AVAILABLE = False

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=['http://localhost:5500', 'http://127.0.0.1:5500'])

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-super-secret-key-change-in-production')

@dataclass
class DatabaseContext:
    """Stores database information for RAG context"""
    doctors: List[Dict]
    departments: List[Dict]
    available_slots: List[Dict]
    recent_appointments: List[Dict]

class EnhancedConversationManager:
    """Enhanced conversation management with RAG capabilities"""
    
    def __init__(self):
        self.conversations = {}
        self.db_context_cache = {}
        self.cache_expiry = 300  # 5 minutes
        
        # Initialize RAG components if available
        if RAG_AVAILABLE:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.vector_store = None
            self.corpus_texts = []
            self._initialize_vector_store()
        else:
            self.embedding_model = None
            self.vector_store = None
    
    def _get_db_connection(self):
        """Get database connection with error handling"""
        try:
            return psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'hospital'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres')
            )
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            return None
    
    def _execute_query(self, query: str, params: tuple = None) -> Optional[List[Dict]]:
        """Execute database query with error handling"""
        conn = self._get_db_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, params)
            result = cursor.fetchall()
            cursor.close()
            conn.close()
            return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"Database query error: {e}")
            if conn:
                conn.close()
            return None
    
    def _get_database_context(self) -> DatabaseContext:
        """Get current database context with corrected column names"""
        current_time = datetime.now()
        cache_key = 'db_context'
        
        # Check cache
        if cache_key in self.db_context_cache:
            cached_time, cached_data = self.db_context_cache[cache_key]
            if (current_time - cached_time).seconds < self.cache_expiry:
                return cached_data
        
        logger.info("Refreshing database context for RAG")
        
        # Get doctors with corrected column names
        doctors_query = """
        SELECT d.id, 
               CONCAT(d.first_name, ' ', d.last_name) as name,
               s.name as specialization, 
               d.experience_years, 
               d.consultation_fee, 
               d.phone, 
               d.email,
               s.name as department,
               d.is_active
        FROM doctors d
        JOIN specializations s ON d.specialization_id = s.id
        WHERE d.is_active = true
        ORDER BY s.name, d.last_name
        """
        
        # Get departments (specializations)
        departments_query = """
        SELECT s.id, s.name, s.description,
               COUNT(d.id) as doctor_count
        FROM specializations s
        LEFT JOIN doctors d ON s.id = d.specialization_id AND d.is_active = true
        GROUP BY s.id, s.name, s.description
        ORDER BY s.name
        """
        
        # Get available slots with corrected column names
        available_slots_query = """
        SELECT da.id, da.doctor_id, 
               CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
               s.name as specialization,
               da.day_of_week, da.start_time, da.end_time, da.slot_duration,
               da.is_active
        FROM doctor_availability da
        JOIN doctors d ON da.doctor_id = d.id
        JOIN specializations s ON d.specialization_id = s.id
        WHERE da.is_active = true AND d.is_active = true
        ORDER BY da.day_of_week, da.start_time
        """
        
        # Get recent appointments with corrected column names
        recent_appointments_query = """
        SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.reason_for_visit,
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
        
        # Execute queries
        doctors = self._execute_query(doctors_query) or []
        departments = self._execute_query(departments_query) or []
        available_slots = self._execute_query(available_slots_query) or []
        recent_appointments = self._execute_query(recent_appointments_query) or []
        
        # Create context object
        db_context = DatabaseContext(
            doctors=doctors,
            departments=departments,
            available_slots=available_slots,
            recent_appointments=recent_appointments
        )
        
        # Cache the result
        self.db_context_cache[cache_key] = (current_time, db_context)
        
        return db_context
    
    def _initialize_vector_store(self):
        """Initialize FAISS vector store with database content"""
        if not RAG_AVAILABLE:
            return
        
        try:
            db_context = self._get_database_context()
            
            # Create corpus from database content
            corpus_texts = []
            
            # Add doctor information
            for doctor in db_context.doctors:
                text = f"Dr. {doctor['name']} is a {doctor['specialization']} specialist with {doctor.get('experience_years', 'unknown')} years of experience. Consultation fee: ${doctor.get('consultation_fee', 'N/A')}. Contact: {doctor.get('phone', 'N/A')}"
                corpus_texts.append(text)
            
            # Add department information
            for dept in db_context.departments:
                text = f"{dept['name']} department: {dept.get('description', 'Medical specialty')}. Number of doctors: {dept.get('doctor_count', 0)}"
                corpus_texts.append(text)
            
            # Add availability information
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            for slot in db_context.available_slots:
                day_name = day_names[slot['day_of_week']]
                text = f"Dr. {slot['doctor_name']} ({slot['specialization']}) is available on {day_name} from {slot['start_time']} to {slot['end_time']}"
                corpus_texts.append(text)
            
            if not corpus_texts:
                logger.warning("No database content found for vector store")
                return
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(corpus_texts)
            
            # Create FAISS index
            dimension = embeddings.shape[1]
            self.vector_store = faiss.IndexFlatL2(dimension)
            self.vector_store.add(embeddings.astype('float32'))
            self.corpus_texts = corpus_texts
            
            logger.info(f"Initialized vector store with {len(corpus_texts)} documents")
            
        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            self.vector_store = None
    
    def _get_relevant_context(self, query: str, k: int = 5) -> str:
        """Get relevant context using RAG"""
        if not RAG_AVAILABLE or not self.vector_store:
            return ""
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query])
            
            # Search for similar documents
            distances, indices = self.vector_store.search(query_embedding.astype('float32'), k)
            
            # Get relevant texts
            relevant_texts = []
            for idx in indices[0]:
                if idx < len(self.corpus_texts):
                    relevant_texts.append(self.corpus_texts[idx])
            
            return "\n".join(relevant_texts)
            
        except Exception as e:
            logger.error(f"Error in RAG retrieval: {e}")
            return ""
    
    def get_conversation(self, session_id: str) -> List[Dict]:
        """Get conversation history"""
        return self.conversations.get(session_id, [])
    
    def add_message(self, session_id: str, user_message: str, ai_response: str):
        """Add message to conversation history"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        self.conversations[session_id].append({
            'timestamp': datetime.now().isoformat(),
            'user': user_message,
            'ai': ai_response
        })
        
        # Keep only last 10 messages
        self.conversations[session_id] = self.conversations[session_id][-10:]
    
    def process_message(self, user_message: str, session_id: str) -> Dict:
        """Process user message with enhanced AI and RAG"""
        try:
            # Validate input
            if not user_message or not user_message.strip():
                return {
                    'response': "I didn't receive a message. Could you please ask me something?",
                    'session_id': session_id,
                    'success': True
                }
            
            user_message = user_message.strip()
            
            # Get database context
            db_context = self._get_database_context()
            
            # Get relevant context using RAG
            rag_context = self._get_relevant_context(user_message)
            
            # Build enhanced system prompt
            system_prompt = f"""You are a helpful AI assistant for a hospital appointment booking system.

Current Database Context:
- We have {len(db_context.doctors)} active doctors
- Available specializations: {', '.join([d['name'] for d in db_context.departments])}
- Recent appointments: {len(db_context.recent_appointments)} in the last week

Relevant Information:
{rag_context}

You can help with:
1. Finding doctors by specialty
2. Checking availability 
3. Booking appointments
4. General medical information
5. Hospital information

Be helpful, professional, and provide specific information when available. If you need to book an appointment, ask for necessary details like patient name, preferred doctor/specialty, and preferred time."""

            # Get conversation history
            conversation_history = self.get_conversation(session_id)
            
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
                    doc_list = ', '.join([f"Dr. {d['name']}" for d in cardiologists[:3]])
                    return f"We have several cardiologists available: {doc_list}. Would you like to book an appointment with any of them?"
            
            elif 'neurologist' in user_lower or 'brain' in user_lower:
                neurologists = [d for d in db_context.doctors if 'neuro' in d['specialization'].lower()]
                if neurologists:
                    doc_list = ', '.join([f"Dr. {d['name']}" for d in neurologists[:3]])
                    return f"Our neurology department has: {doc_list}. Which doctor would you prefer?"
            
            # General doctor list
            return f"We have {len(db_context.doctors)} doctors available across {len(db_context.departments)} departments. What type of specialist are you looking for?"
        
        # Appointment booking
        elif any(word in user_lower for word in ['book', 'appointment', 'schedule']):
            return f"I'd be happy to help you book an appointment! We have {len(db_context.available_slots)} available slots. What type of doctor do you need to see?"
        
        # Availability inquiry
        elif any(word in user_lower for word in ['available', 'availability', 'free', 'open']):
            return f"We have doctors available across {len(db_context.departments)} specializations. What specialty are you interested in?"
        
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
    """Get all appointments with corrected column names"""
    try:
        query = """
        SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.reason_for_visit,
               CONCAT(p.first_name, ' ', p.last_name) as patient_name, 
               p.phone as patient_phone,
               CONCAT(d.first_name, ' ', d.last_name) as doctor_name, 
               s.name as specialization,
               s.name as department
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN specializations s ON d.specialization_id = s.id
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 50
        """
        
        appointments = execute_sql_query(query)
        
        if appointments is None:
            return jsonify([])  # Return empty array if no appointments
        
        # Format appointments for frontend
        formatted_appointments = []
        for apt in appointments:
            formatted_appointments.append({
                'id': apt['id'],
                'date': apt['appointment_date'].isoformat() if apt['appointment_date'] else None,
                'time': str(apt['appointment_time']) if apt['appointment_time'] else None,
                'appointment_time': str(apt['appointment_time']) if apt['appointment_time'] else 'Time TBD',
                'status': apt['status'] or 'scheduled',
                'reason': apt['reason_for_visit'],
                'patient_name': apt['patient_name'],
                'patient_phone': apt['patient_phone'],
                'doctor_name': apt['doctor_name'],
                'specialization': apt['specialization'],
                'department': apt['department']
            })
        
        return jsonify(formatted_appointments)
        
    except Exception as e:
        logger.error(f"Error fetching appointments: {e}")
        return jsonify([])

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    """Get all doctors with availability info and corrected column names"""
    try:
        specialty = request.args.get('specialty')
        
        query = """
        SELECT d.id, 
               CONCAT(d.first_name, ' ', d.last_name) as name,
               s.name as specialization, 
               d.experience_years, 
               d.consultation_fee, 
               d.phone, 
               d.email,
               s.name as department,
               COUNT(da.id) as available_slots
        FROM doctors d
        JOIN specializations s ON d.specialization_id = s.id
        LEFT JOIN doctor_availability da ON d.id = da.doctor_id 
            AND da.is_active = true
        WHERE d.is_active = true
        """
        
        params = []
        if specialty:
            query += " AND s.name ILIKE %s"
            params.append(f"%{specialty}%")
        
        query += " GROUP BY d.id, d.first_name, d.last_name, s.name, d.experience_years, d.consultation_fee, d.phone, d.email ORDER BY s.name, d.last_name"
        
        doctors = execute_sql_query(query, tuple(params))
        
        return jsonify({
            'doctors': doctors or [],
            'success': True
        })
        
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        return jsonify({
            'doctors': [],
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/departments', methods=['GET'])
def get_departments():
    """Get all departments (specializations) with corrected column names"""
    try:
        query = """
        SELECT s.id, s.name, s.description,
               COUNT(d.id) as doctor_count
        FROM specializations s
        LEFT JOIN doctors d ON s.id = d.specialization_id AND d.is_active = true
        GROUP BY s.id, s.name, s.description
        ORDER BY s.name
        """
        
        departments = execute_sql_query(query)
        
        return jsonify({
            'departments': departments or [],
            'success': True
        })
        
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return jsonify({
            'departments': [],
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/patients', methods=['GET'])
def get_patients():
    """Get all patients with corrected column names"""
    try:
        query = """
        SELECT p.id, 
               CONCAT(p.first_name, ' ', p.last_name) as name,
               p.email, p.phone, p.date_of_birth, p.gender,
               p.address, p.emergency_contact_name, p.emergency_contact_phone,
               p.is_active, p.created_at
        FROM patients p
        WHERE p.is_active = true
        ORDER BY p.last_name, p.first_name
        """
        
        patients = execute_sql_query(query)
        
        return jsonify({
            'patients': patients or [],
            'success': True
        })
        
    except Exception as e:
        logger.error(f"Error fetching patients: {e}")
        return jsonify({
            'patients': [],
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_status = execute_sql_query("SELECT 1 as test")
        db_connected = db_status is not None
        
        # Test Bedrock connection if available
        bedrock_connected = BEDROCK_AVAILABLE
        if BEDROCK_AVAILABLE:
            try:
                bedrock_client = get_bedrock_client()
                bedrock_connected = bedrock_client is not None
            except:
                bedrock_connected = False
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected' if db_connected else 'disconnected',
            'ai_service': 'connected' if bedrock_connected else 'disconnected',
            'rag_enabled': RAG_AVAILABLE,
            'bedrock_enabled': BEDROCK_AVAILABLE,
            'vector_store': 'initialized' if conversation_manager.vector_store else 'not_initialized',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'success': False
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'success': False
    }), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Enhanced DocAI System")
    logger.info("=" * 50)
    
    # System status
    logger.info(f"✅ Database integration: Enabled")
    logger.info(f"{'✅' if RAG_AVAILABLE else '❌'} RAG capabilities: {'Enabled' if RAG_AVAILABLE else 'Disabled (install sentence-transformers faiss-cpu)'}")
    logger.info(f"{'✅' if BEDROCK_AVAILABLE else '❌'} AWS Bedrock: {'Enabled' if BEDROCK_AVAILABLE else 'Disabled (check bedrock.py)'}")
    
    # Test system initialization
    try:
        db_context = conversation_manager._get_database_context()
        logger.info(f"✅ Database context loaded: {len(db_context.doctors)} doctors, {len(db_context.departments)} departments")
        
        if conversation_manager.vector_store:
            logger.info("✅ Vector store initialized for RAG")
        else:
            logger.warning("⚠️ Vector store not initialized - RAG features limited")
            
    except Exception as e:
        logger.error(f"❌ System initialization error: {e}")
    
    logger.info("🌐 Starting server on http://localhost:8000")
    logger.info("📱 Frontend should be available on http://localhost:5500")
    
    app.run(debug=True, host='0.0.0.0', port=8000)