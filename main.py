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
                database=os.getenv('DB_NAME', 'doctor_ai'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'password')
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
            cursor.execute(query, params or ())
            
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
                return [dict(row) for row in result]
            else:
                conn.commit()
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def _get_database_context(self) -> DatabaseContext:
        """Retrieve comprehensive database context for RAG"""
        current_time = datetime.now()
        
        # Check cache
        if ('last_updated' in self.db_context_cache and 
            (current_time - self.db_context_cache['last_updated']).seconds < self.cache_expiry):
            return self.db_context_cache['context']
        
        # Fetch fresh data
        logger.info("Refreshing database context for RAG")
        
        # Get active doctors with departments
        doctors_query = """
        SELECT d.id, d.name, d.specialization, d.experience_years, d.consultation_fee,
               dep.name as department, d.phone, d.email
        FROM doctors d
        JOIN departments dep ON d.department_id = dep.id
        WHERE d.is_active = true
        ORDER BY d.specialization, d.name
        """
        doctors = self._execute_query(doctors_query) or []
        
        # Get departments
        departments_query = """
        SELECT id, name, description
        FROM departments
        WHERE is_active = true
        ORDER BY name
        """
        departments = self._execute_query(departments_query) or []
        
        # Get available appointment slots (next 30 days)
        slots_query = """
        SELECT ds.id, ds.date, ds.start_time, ds.end_time,
               d.name as doctor_name, d.specialization,
               dep.name as department
        FROM doctor_schedules ds
        JOIN doctors d ON ds.doctor_id = d.id
        JOIN departments dep ON d.department_id = dep.id
        WHERE ds.date >= CURRENT_DATE 
        AND ds.date <= CURRENT_DATE + INTERVAL '30 days'
        AND ds.is_available = true
        ORDER BY ds.date, ds.start_time
        LIMIT 100
        """
        available_slots = self._execute_query(slots_query) or []
        
        # Get recent appointments for context
        recent_appointments_query = """
        SELECT a.id, a.date, a.time, a.status,
               p.name as patient_name, p.phone as patient_phone,
               d.name as doctor_name, d.specialization,
               dep.name as department
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN departments dep ON d.department_id = dep.id
        WHERE a.date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY a.date DESC, a.time DESC
        LIMIT 20
        """
        recent_appointments = self._execute_query(recent_appointments_query) or []
        
        context = DatabaseContext(
            doctors=doctors,
            departments=departments,
            available_slots=available_slots,
            recent_appointments=recent_appointments
        )
        
        # Cache the context
        self.db_context_cache = {
            'context': context,
            'last_updated': current_time
        }
        
        return context
    
    def _initialize_vector_store(self):
        """Initialize FAISS vector store with database information"""
        if not RAG_AVAILABLE:
            return
        
        try:
            context = self._get_database_context()
            
            # Create text corpus from database
            texts = []
            
            # Add doctor information
            for doctor in context.doctors:
                text = f"Dr. {doctor['name']} is a {doctor['specialization']} in the {doctor['department']} department with {doctor['experience_years']} years of experience. Consultation fee: ${doctor['consultation_fee']}"
                texts.append(text)
            
            # Add department information
            for dept in context.departments:
                text = f"{dept['name']} department: {dept['description']}"
                texts.append(text)
            
            # Add appointment availability info
            for slot in context.available_slots[:20]:  # Limit for performance
                text = f"Available appointment with Dr. {slot['doctor_name']} ({slot['specialization']}) on {slot['date']} at {slot['start_time']}"
                texts.append(text)
            
            if texts:
                # Generate embeddings
                embeddings = self.embedding_model.encode(texts)
                
                # Create FAISS index
                dimension = embeddings.shape[1]
                self.vector_store = faiss.IndexFlatL2(dimension)
                self.vector_store.add(embeddings.astype('float32'))
                self.corpus_texts = texts
                
                logger.info(f"Initialized vector store with {len(texts)} documents")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
    
    def _retrieve_context(self, query: str, k: int = 5) -> List[str]:
        """Retrieve relevant context using vector similarity search"""
        if not self.vector_store or not RAG_AVAILABLE:
            return []
        
        try:
            # Encode query
            query_embedding = self.embedding_model.encode([query])
            
            # Search for similar documents
            distances, indices = self.vector_store.search(query_embedding.astype('float32'), k)
            
            # Return relevant texts
            relevant_texts = [self.corpus_texts[idx] for idx in indices[0] if idx < len(self.corpus_texts)]
            return relevant_texts
        
        except Exception as e:
            logger.error(f"Error in context retrieval: {e}")
            return []
    
    def _build_enhanced_system_prompt(self, relevant_context: List[str], db_context: DatabaseContext, user_message: str) -> str:
        """Build comprehensive system prompt with RAG context"""
        
        # Get current availability summary
        available_today = [slot for slot in db_context.available_slots if slot['date'] == datetime.now().date()]
        
        system_prompt = f"""You are an AI medical assistant for a hospital appointment booking system. You help patients book appointments, find doctors, reschedule appointments, and answer healthcare questions.

CURRENT DATABASE CONTEXT:
- Available doctors: {len(db_context.doctors)} active doctors across {len(db_context.departments)} departments
- Available appointments today: {len(available_today)} slots
- Recent activity: {len(db_context.recent_appointments)} appointments in past week

RELEVANT INFORMATION FOR THIS QUERY:
{chr(10).join(relevant_context) if relevant_context else "No specific context retrieved"}

AVAILABLE DEPARTMENTS:
{chr(10).join([f"• {dept['name']}: {dept['description']}" for dept in db_context.departments])}

GUIDELINES:
1. Be helpful, professional, and empathetic
2. Use the database context to provide accurate, real-time information
3. For appointment booking, collect: patient name, phone, preferred specialty/doctor, reason for visit
4. Always verify doctor availability before confirming appointments
5. Provide specific doctor names, specializations, and available times when possible
6. If no suitable appointment is available, suggest alternatives
7. Handle rescheduling and cancellation requests appropriately
8. Answer general health questions but always recommend consulting with healthcare professionals

CAPABILITIES:
- Book new appointments with real-time availability checking
- Find doctors by specialty or name
- Provide department information and doctor details
- Reschedule or cancel existing appointments
- Answer basic health questions
- Check appointment availability

User's message: "{user_message}"

Remember to be conversational and helpful while being accurate with the database information."""

        return system_prompt
    
    def generate_enhanced_response(self, user_message: str, session_id: str = None) -> Dict:
        """Generate enhanced AI response using RAG and database context"""
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        try:
            # Get database context
            db_context = self._get_database_context()
            
            # Retrieve relevant context using RAG (if available)
            relevant_context = self._retrieve_context(user_message) if RAG_AVAILABLE else []
            
            # Build enhanced system prompt
            system_prompt = self._build_enhanced_system_prompt(relevant_context, db_context, user_message)
            
            # Get conversation history
            conversation_history = self.conversations.get(session_id, [])
            
            # Generate AI response
            if BEDROCK_AVAILABLE:
                ai_response = get_ai_response(system_prompt, user_message, conversation_history[-5:])
            else:
                # Fallback to enhanced rule-based system if Bedrock not available
                ai_response = self._generate_fallback_response(user_message, db_context)
            
            # Update conversation history
            if session_id not in self.conversations:
                self.conversations[session_id] = []
            
            self.conversations[session_id].extend([
                {'type': 'user', 'content': user_message, 'timestamp': datetime.now().isoformat()},
                {'type': 'ai', 'content': ai_response, 'timestamp': datetime.now().isoformat()}
            ])
            
            # Keep only last 20 messages per conversation
            if len(self.conversations[session_id]) > 20:
                self.conversations[session_id] = self.conversations[session_id][-20:]
            
            return {
                'response': ai_response,
                'session_id': session_id,
                'context': {
                    'available_doctors': len(db_context.doctors),
                    'available_slots': len(db_context.available_slots),
                    'relevant_context_retrieved': len(relevant_context),
                    'rag_enabled': RAG_AVAILABLE,
                    'bedrock_enabled': BEDROCK_AVAILABLE
                },
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error generating enhanced response: {e}")
            return {
                'response': "I apologize, but I encountered an error processing your request. Please try again.",
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
            return f"I'd be happy to help you book an appointment! We have {len(db_context.available_slots)} available slots in the next 30 days. What type of doctor do you need to see?"
        
        # Availability inquiry
        elif any(word in user_lower for word in ['available', 'availability', 'free', 'open']):
            today_slots = [s for s in db_context.available_slots if s['date'] == datetime.now().date()]
            return f"Today we have {len(today_slots)} available appointment slots. This week we have {len(db_context.available_slots)} total slots available. What specialty are you interested in?"
        
        # Default response with context
        else:
            return f"Hello! I'm your AI healthcare assistant. I can help you book appointments with our {len(db_context.doctors)} doctors, find specialists, or answer health questions. How can I assist you today?"

# Initialize the enhanced conversation manager
conversation_manager = EnhancedConversationManager()

# Keep your existing utility functions
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'doctor_ai'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password')
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def execute_sql_query(query, params=None):
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params or ())
        
        if query.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
        else:
            result = cursor.fetchone()
            conn.commit()
        
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f"Database query error: {e}")
        return None

# Enhanced Flask routes
@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """Enhanced chat endpoint with RAG"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not user_message:
            return jsonify({'error': 'Message is required', 'success': False}), 400
        
        # Process message with enhanced conversation manager
        result = conversation_manager.generate_enhanced_response(user_message, session_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'success': False
        }), 500

@app.route('/api/appointments', methods=['GET'])
def get_appointments():
    """Get all appointments with proper error handling"""
    try:
        query = """
        SELECT a.id, a.date, a.time, a.status, a.reason,
               p.name as patient_name, p.phone as patient_phone,
               d.name as doctor_name, d.specialization,
               dep.name as department
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN departments dep ON d.department_id = dep.id
        ORDER BY a.date DESC, a.time DESC
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
                'date': apt['date'].isoformat() if apt['date'] else None,
                'time': str(apt['time']) if apt['time'] else None,
                'appointment_time': str(apt['time']) if apt['time'] else 'Time TBD',
                'status': apt['status'] or 'scheduled',
                'reason': apt['reason'],
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
    """Get all doctors with availability info"""
    try:
        specialty = request.args.get('specialty')
        
        query = """
        SELECT d.id, d.name, d.specialization, d.experience_years, 
               d.consultation_fee, d.phone, d.email,
               dep.name as department,
               COUNT(ds.id) as available_slots
        FROM doctors d
        JOIN departments dep ON d.department_id = dep.id
        LEFT JOIN doctor_schedules ds ON d.id = ds.doctor_id 
            AND ds.date >= CURRENT_DATE 
            AND ds.is_available = true
        WHERE d.is_active = true
        """
        
        params = []
        if specialty:
            query += " AND d.specialization ILIKE %s"
            params.append(f"%{specialty}%")
        
        query += " GROUP BY d.id, d.name, d.specialization, d.experience_years, d.consultation_fee, d.phone, d.email, dep.name ORDER BY d.specialization, d.name"
        
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
    """Get all departments"""
    try:
        query = """
        SELECT d.id, d.name, d.description,
               COUNT(doc.id) as doctor_count
        FROM departments d
        LEFT JOIN doctors doc ON d.id = doc.department_id AND doc.is_active = true
        WHERE d.is_active = true
        GROUP BY d.id, d.name, d.description
        ORDER BY d.name
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