# Doc-AI - AI-Powered Healthcare Management System

Doc-AI is a comprehensive hospital appointment management system that leverages **Flask** with **AWS Bedrock** (Claude AI) and **RAG (Retrieval-Augmented Generation)** capabilities to provide intelligent natural language querying of a hospital appointment database. The system features a modern React frontend for seamless user interaction.

## 🏗️ Architecture

- **Backend**: Flask with PostgreSQL database and RESTful API
- **AI Engine**: AWS Bedrock (Claude 3 Sonnet) with RAG enhancement
- **Frontend**: Modern React with React Router and responsive design
- **Database**: PostgreSQL with comprehensive medical schema
- **Vector Store**: FAISS for semantic search capabilities
- **Chat Interface**: Real-time AI assistant with conversation memory

## ✨ Features

### 🤖 AI-Powered Natural Language Interface
- Ask questions in plain English about appointments, doctors, and availability
- RAG-enhanced responses using vector embeddings for contextual accuracy
- Conversation memory for improved user experience across sessions
- Intelligent intent analysis for appointment booking and management
- Support for complex medical queries and scheduling requests

### 🏥 Hospital Management System
- **Appointment Management**: Book, reschedule, cancel appointments with real-time updates
- **Doctor Scheduling**: Manage doctor availability and schedules across departments
- **Department Organization**: Organize doctors by medical specialties with detailed profiles
- **Patient Records**: Comprehensive patient information management
- **Admin Dashboard**: Full appointment overview and system management tools
- **Real-time Status Updates**: Live appointment status tracking

### 🔧 Advanced Technical Features
- Vector embeddings with sentence-transformers for semantic understanding
- FAISS vector store for efficient similarity search
- Real-time database context caching for improved performance
- Comprehensive error handling and logging throughout the system
- Production-ready Flask configuration with security best practices
- Responsive design that works on desktop, tablet, and mobile devices

## 📋 Prerequisites

### Required Software
- **Python 3.8+** (Python 3.13+ recommended)
- **PostgreSQL 12+** (PostgreSQL 15+ recommended)
- **Node.js 16+** and npm for frontend dependencies
- **Git** for version control

### AWS Requirements
- **AWS Account** with Bedrock access enabled
- **AWS CLI** configured (optional but recommended for easier credential management)
- **Claude 3 Sonnet** model access in your AWS region

### System Requirements
- **Memory**: At least 4GB RAM (8GB+ recommended for vector operations)
- **Storage**: At least 2GB free space for dependencies and vector stores
- **Network**: Stable internet connection for AWS Bedrock API calls

## 🚀 Installation & Setup

### 1. Clone Repository and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd doc-ai

# Create and activate virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip3 install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Database Setup

```bash
# Create PostgreSQL database
createdb hospital

# Alternative: Using psql
psql -c "CREATE DATABASE hospital;"

# Set up database schema and populate with sample data
python3 setup_database.py

# Verify database connection and setup
python3 test_database.py
```

### 3. Environment Configuration

Create a `.env` file in the project root with the following configuration:

```bash
# Database Configuration
DB_HOST=localhost
DB_NAME=hospital
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_PORT=5432

# AWS Bedrock Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key

# Flask Configuration
FLASK_SECRET_KEY=your-super-secret-key-change-in-production
FLASK_ENV=development
FLASK_DEBUG=True

# Optional: Redis Configuration (for advanced chat history)
REDIS_URL=redis://localhost:6379/0
```

### 4. AWS Bedrock Setup

**Step 1: Enable Model Access**
1. Log into AWS Console → Amazon Bedrock → Model Access
2. Request access to `anthropic.claude-3-sonnet-20240229-v1:0`
3. Wait for approval (usually immediate for supported regions)

**Step 2: Configure Credentials**
Choose one of these methods:

**Option A: Environment Variables** (recommended for development)
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

**Option B: AWS CLI Configuration**
```bash
aws configure
# Follow prompts to enter your credentials
```

**Option C: IAM Roles** (recommended for production)
- Attach appropriate IAM role to your EC2 instance or container

### 5. Verify Installation

```bash
# Test database connection
python3 test_database.py

# Test AWS Bedrock connection
python3 -c "
import boto3
try:
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    print('✅ AWS Bedrock connection successful')
except Exception as e:
    print(f'❌ AWS Bedrock connection failed: {e}')
"

# Check required Python packages
python3 -c "
import flask, psycopg2, boto3, sentence_transformers, faiss
print('✅ All required packages installed')
"
```

## 🏃‍♂️ Running the Application

### Development Mode

**Terminal 1: Start the Backend Server**
```bash
# Activate virtual environment if not already active
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Start Flask backend
python3 main.py
```

**Terminal 2: Start the Frontend**
```bash
cd frontend
npm start
# Alternative: Use serve directly
npx serve -l 5500 public
```

### Production Mode

```bash
# Build optimized frontend
cd frontend
npm run build

# Start production backend
FLASK_ENV=production python3 main.py
```

### System Status Verification

Once both servers are running, you should see:

**Backend Status (http://localhost:8000/api/health):**
```json
{
  "status": "healthy",
  "database": "connected",
  "ai_service": "connected",
  "rag_enabled": true,
  "bedrock_enabled": true,
  "vector_store": "initialized"
}
```

**Frontend Status:**
- ✅ Database integration: Enabled
- ✅ RAG capabilities: Enabled
- ✅ AWS Bedrock: Enabled
- ✅ Vector store: Initialized

## 🌐 Application URLs

- **Main Application**: http://localhost:5500
- **Backend API**: http://localhost:8000
- **Health Check**: http://localhost:8000/api/health
- **API Documentation**: Available through endpoint testing

## 📡 API Reference

### Core AI Endpoints

| Method | Endpoint | Description | Example |
|--------|----------|-------------|---------|
| `POST` | `/ask` | Natural language AI queries | `{"question": "Book appointment with cardiologist"}` |
| `GET` | `/api/health` | System health and status | Returns health status JSON |

### Appointment Management

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/api/appointments` | List user appointments | `?patient_id=123` |
| `POST` | `/api/appointments` | Create new appointment | JSON body with appointment details |
| `PUT` | `/api/appointments/{id}` | Update appointment | JSON body with updated details |
| `DELETE` | `/api/appointments/{id}` | Cancel appointment | Appointment ID in URL |
| `GET` | `/api/admin/appointments` | Admin: All appointments | Requires admin access |

### Doctor & Department Management

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/api/doctors` | List doctors with availability | `?department_id=1&available_date=2024-01-15` |
| `GET` | `/api/departments` | List departments with doctor counts | None |
| `GET` | `/api/doctor_schedule` | Doctor availability schedules | `?doctor_id=123&date_range=week` |

### Patient Management

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/api/patients` | List all patients | `?search=john&limit=50` |
| `POST` | `/api/patients` | Register new patient | JSON body with patient details |
| `PUT` | `/api/patients/{id}` | Update patient info | JSON body with updated details |

## 🤖 AI Query Examples

Try these natural language queries in the chat interface:

### Booking Appointments
```
"Book an appointment with Dr. Smith for next Tuesday at 2 PM"
"I need to see a cardiologist this week"
"Schedule me with the earliest available orthopedic doctor"
"Book a follow-up appointment with my neurologist"
```

### Finding Doctors
```
"Show me all cardiologists available this week"
"Which doctors specialize in pediatrics?"
"Find me a neurologist who's available on Friday"
"What are the consultation fees for orthopedic doctors?"
```

### Managing Appointments
```
"Show my upcoming appointments"
"Cancel my appointment on Friday"
"Reschedule my Tuesday appointment to next week"
"What's my appointment status with Dr. Johnson?"
```

### Availability Queries
```
"What's the next available slot in the neurology department?"
"Show me all available times with Dr. Martinez this month"
"When is the cardiology department least busy?"
"Find me weekend appointment slots"
```

## 🗄️ Database Schema

### Core Tables

**departments**
- `id` (Primary Key)
- `name` - Department name (e.g., "Cardiology")
- `description` - Detailed department description
- `created_at` - Timestamp

**doctors**
- `id` (Primary Key)
- `name` - Doctor's full name
- `specialization` - Medical specialty
- `department_id` - Foreign key to departments
- `consultation_fee` - Fee amount
- `phone`, `email` - Contact information
- `experience_years` - Years of experience

**patients**
- `id` (Primary Key)
- `name` - Patient's full name
- `date_of_birth` - Birth date
- `gender` - Gender
- `phone`, `email` - Contact information
- `address` - Full address
- `created_at` - Registration timestamp

**appointments**
- `id` (Primary Key)
- `patient_id` - Foreign key to patients
- `doctor_id` - Foreign key to doctors
- `appointment_date` - Date of appointment
- `appointment_time` - Time of appointment
- `status` - Status (scheduled, completed, cancelled)
- `reason` - Reason for visit
- `notes` - Additional notes

**doctor_schedules**
- `id` (Primary Key)
- `doctor_id` - Foreign key to doctors
- `day_of_week` - Day (0=Sunday, 6=Saturday)
- `start_time` - Availability start time
- `end_time` - Availability end time
- `is_available` - Boolean availability flag

### Sample Data

The system includes comprehensive sample data:
- **5 Medical Departments**: Cardiology, Neurology, Orthopedics, Pediatrics, General Medicine
- **12+ Doctors**: Specialists across different departments with realistic profiles
- **Sample Patients**: Test patient records with diverse demographics
- **Available Slots**: Pre-configured appointment availability across multiple time slots

## 🔧 Advanced Configuration

### RAG (Retrieval-Augmented Generation) Setup

The system implements advanced RAG capabilities:

1. **Vector Embeddings**: Using `sentence-transformers/all-MiniLM-L6-v2` model
2. **Vector Store**: FAISS for efficient similarity search and retrieval
3. **Context Retrieval**: Real-time database context for AI responses
4. **Semantic Search**: Enhanced query understanding and response accuracy

### Performance Optimization

```python
# In main.py, configure these settings for production:
app.config['DATABASE_POOL_SIZE'] = 20
app.config['DATABASE_POOL_TIMEOUT'] = 30
app.config['VECTOR_CACHE_SIZE'] = 1000
```

### Security Configuration

```bash
# Production environment variables
FLASK_ENV=production
FLASK_DEBUG=False
FLASK_SECRET_KEY=complex-random-key-here
SSL_CERT_PATH=/path/to/ssl/cert.pem
SSL_KEY_PATH=/path/to/ssl/key.pem
```

## 📦 Dependencies

### Backend (Python)
```text
flask>=2.3.0                 # Web framework
flask-cors>=4.0.0            # Cross-origin resource sharing
psycopg2-binary>=2.9.0       # PostgreSQL adapter
boto3>=1.26.0                # AWS SDK
sentence-transformers>=2.2.0  # Vector embeddings
faiss-cpu>=1.7.4             # Vector similarity search
python-dotenv>=1.0.0         # Environment management
langchain-aws>=0.1.0         # LangChain AWS integration
langchain-core>=0.1.0        # LangChain core components
pydantic>=2.0.0              # Data validation
numpy>=1.24.0                # Numerical computing
requests>=2.31.0             # HTTP requests
```

### Frontend (JavaScript)
```json
{
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "react-router-dom": "^6.30.1",
  "serve": "^14.2.0"
}
```

## 🚨 Troubleshooting

### Common Issues and Solutions

#### 1. Database Connection Errors
```bash
# Test database connection
python3 test_database.py

# Common fixes:
sudo systemctl start postgresql
createdb hospital
```

#### 2. AWS Bedrock Access Denied
```bash
# Verify credentials
aws sts get-caller-identity

# Check Bedrock model access
aws bedrock list-foundation-models --region us-east-1

# Common fixes:
aws configure
# Update IAM permissions for Bedrock access
```

#### 3. Python Dependencies Issues
```bash
# Clean install
pip3 uninstall -r requirements.txt -y
pip3 install -r requirements.txt

# If sentence-transformers fails:
pip3 install torch --index-url https://download.pytorch.org/whl/cpu
pip3 install sentence-transformers
```

#### 4. Frontend Issues
```bash
# Clear npm cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install

# If serve command not found:
npm install -g serve
```

#### 5. Port Conflicts
```bash
# Find processes using ports
lsof -ti:8000  # Backend port
lsof -ti:5500  # Frontend port

# Kill processes if needed
kill -9 $(lsof -ti:8000)
```

### Health Check Commands

```bash
# Complete system health check
python3 -c "
import requests
try:
    r = requests.get('http://localhost:8000/api/health')
    print('✅ Backend:', r.json())
except:
    print('❌ Backend not responding')

try:
    r = requests.get('http://localhost:5500')
    print('✅ Frontend: Accessible')
except:
    print('❌ Frontend not accessible')
"
```

## 🔒 Security Best Practices

### Development
- Use virtual environments for Python dependencies
- Keep `.env` files out of version control
- Use strong, unique secret keys
- Enable CORS only for trusted domains

### Production
- Use HTTPS/TLS encryption
- Implement rate limiting for API endpoints
- Use AWS IAM roles instead of access keys
- Enable database connection pooling
- Implement proper authentication and authorization
- Use environment-specific configuration
- Regular security updates for all dependencies

## 📈 Production Deployment

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up --build

# Production deployment
docker-compose -f docker-compose-prod.yml up -d
```

### AWS Deployment Considerations
1. **Database**: Use Amazon RDS for PostgreSQL
2. **AI Service**: AWS Bedrock with proper IAM roles
3. **Frontend**: Deploy to S3 + CloudFront
4. **Backend**: Deploy to ECS, Lambda, or EC2
5. **Monitoring**: CloudWatch for logging and metrics
6. **Security**: WAF, VPC, Security Groups

### Performance Monitoring
- Implement health checks for all services
- Monitor database connection pools
- Track AI API usage and costs
- Set up alerting for system failures

## 🧪 Testing

```bash
# Run all tests
python3 -m pytest

# Specific test files
python3 test_database.py
python3 test_booking.py
python3 test_chat.py
python3 test_conversation.py

# Frontend testing
cd frontend
npm test
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Ensure all tests pass: `python3 -m pytest`
5. Submit a pull request with a clear description

## 📄 License

This project is for educational and demonstration purposes. Additional security measures, testing, and optimization would be required for production medical environments.

---

**Note**: This is a demonstration system designed for learning and development. For production medical environments, ensure compliance with HIPAA, implement proper authentication, add comprehensive audit logging, and follow medical data security best practices.