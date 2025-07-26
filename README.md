# Doc-AI

Doc-AI is a comprehensive hospital appointment management system that uses **Flask** with **AWS Bedrock** (Claude AI) and **RAG (Retrieval-Augmented Generation)** capabilities to provide intelligent natural language querying of a hospital appointment database. The system includes a modern React frontend for seamless user interaction.

## 🏗️ Architecture

- **Backend**: Flask with PostgreSQL database
- **AI Engine**: AWS Bedrock (Claude 3 Sonnet) with RAG enhancement
- **Frontend**: React with React Router
- **Database**: PostgreSQL with comprehensive medical schema
- **Vector Store**: FAISS for semantic search capabilities

## 🚀 Features

### AI-Powered Natural Language Interface
- Ask questions in plain English about appointments, doctors, and availability
- RAG-enhanced responses using vector embeddings for contextual accuracy
- Conversation memory for improved user experience
- Intelligent intent analysis for appointment booking

### Hospital Management System
- **Appointment Management**: Book, reschedule, cancel appointments
- **Doctor Scheduling**: Manage doctor availability and schedules
- **Department Organization**: Organize doctors by medical specialties
- **Patient Records**: Comprehensive patient information management
- **Admin Dashboard**: Full appointment overview and system management

### Advanced Technical Features
- Vector embeddings with sentence-transformers
- FAISS vector store for semantic search
- Real-time database context caching
- Comprehensive error handling and logging
- Production-ready Flask configuration

## 📋 Prerequisites

- **Python 3.8+**
- **PostgreSQL 12+**
- **Node.js 16+** and npm
- **AWS Account** with Bedrock access
- **AWS CLI** configured (optional but recommended)

## 🛠️ Setup Instructions

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd doc-ai

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Database Setup

```bash
# Create PostgreSQL database
createdb hospital

# Set up database schema and sample data
python setup_database.py

# Test database connection
python test_database.py
```

### 3. Environment Configuration

Create a `.env` file in the project root:

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
```

### 4. AWS Bedrock Setup

Ensure your AWS account has access to **Claude 3 Sonnet** in AWS Bedrock:

1. Log into AWS Console → Bedrock → Model Access
2. Request access to `anthropic.claude-3-sonnet-20240229-v1:0`
3. Wait for approval (usually immediate for supported regions)

## 🚀 Running the Application

### Start the Backend Server

```bash
python main.py
```

The Flask server will start on `http://localhost:8000`

**System Status Messages:**
- ✅ Database integration: Enabled
- ✅ RAG capabilities: Enabled (if sentence-transformers installed)
- ✅ AWS Bedrock: Enabled (if credentials configured)

### Start the Frontend

```bash
cd frontend
npx serve -l 5500 public
```

The React frontend will be available at `http://localhost:5500`

### Access the Application

- **Main Interface**: http://localhost:5500
- **API Health Check**: http://localhost:8000/api/health
- **API Documentation**: Available through endpoint testing

## 📡 API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ask` | Natural language AI queries |
| `GET` | `/api/health` | System health and status |

### Appointment Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/appointments` | List appointments with details |
| `POST` | `/api/appointments` | Create new appointment |
| `DELETE` | `/api/appointments/{id}` | Cancel appointment |
| `GET` | `/api/admin/appointments` | Admin: Full appointment details |

### Doctor & Department Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/doctors` | List doctors with availability |
| `GET` | `/api/departments` | List departments with doctor counts |
| `GET` | `/api/doctor_schedule` | Doctor availability schedules |

### Patient Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/patients` | List all patients |
| `POST` | `/api/patients` | Register new patient |

## 🤖 AI Query Examples

Try these natural language queries:

```
"Show me all cardiologists available this week"
"Book an appointment with Dr. Smith for next Tuesday"
"What's the next available slot in the neurology department?"
"Cancel my appointment on Friday"
"Which doctors specialize in pediatrics?"
"What are the consultation fees for orthopedic doctors?"
```

## 🔧 Technical Details

### Database Schema

- **departments**: Medical specialties and descriptions
- **doctors**: Doctor profiles with specializations and fees
- **patients**: Patient information and contact details
- **appointments**: Appointment bookings with status tracking
- **doctor_schedules**: Doctor availability and time slots

### RAG Implementation

The system implements advanced RAG (Retrieval-Augmented Generation):

1. **Vector Embeddings**: Using `sentence-transformers/all-MiniLM-L6-v2`
2. **Vector Store**: FAISS for efficient similarity search
3. **Context Retrieval**: Real-time database context for AI responses
4. **Semantic Search**: Enhanced query understanding and response accuracy

### Flask Configuration

- **CORS**: Configured for frontend at `localhost:5500`
- **Error Handling**: Comprehensive error responses
- **Logging**: Detailed logging for debugging and monitoring
- **Security**: Environment-based configuration management

## 📦 Dependencies

### Backend (Python)
- **flask** - Web framework
- **psycopg2-binary** - PostgreSQL adapter
- **boto3** - AWS SDK
- **sentence-transformers** - Vector embeddings
- **faiss-cpu** - Vector similarity search
- **python-dotenv** - Environment management

### Frontend (JavaScript)
- **react** - UI framework
- **react-dom** - React DOM utilities
- **react-router-dom** - Client-side routing
- **serve** - Static file server

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Error**
   ```bash
   python test_database.py
   ```

2. **AWS Bedrock Access Denied**
   - Verify AWS credentials in `.env`
   - Check Bedrock model access in AWS Console

3. **RAG Features Not Working**
   ```bash
   pip install sentence-transformers faiss-cpu
   ```

4. **Frontend Not Loading**
   - Ensure frontend is served on `localhost:5500`
   - Check CORS settings in `main.py`

### Health Check

Visit `http://localhost:8000/api/health` to see system status:

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

## 🏥 Sample Data

The system includes sample data for testing:

- **5 Medical Departments**: Cardiology, Neurology, Orthopedics, Pediatrics, General Medicine
- **12 Doctors**: Specialists across different departments
- **Sample Patients**: Test patient records
- **Available Slots**: Pre-configured appointment availability

## 🔒 Security Notes

- **Environment Variables**: Never commit `.env` files to version control
- **AWS Credentials**: Use IAM roles in production environments
- **Database**: Use connection pooling and proper indexing in production
- **API Security**: Implement authentication and rate limiting for production use

## 📈 Production Considerations

For production deployment:

1. **Database**: Use managed PostgreSQL (AWS RDS, etc.)
2. **AI Service**: Configure proper AWS IAM roles
3. **Frontend**: Build and serve optimized React bundle
4. **Monitoring**: Implement health checks and logging
5. **Security**: Add authentication, HTTPS, and input validation
6. **Scaling**: Consider load balancing and caching strategies

---

**Note**: This is a demonstration system designed for learning and development. Additional security measures, testing, and optimization would be required for production medical environments.