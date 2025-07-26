import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

def create_database_schema():
    """Create database tables and populate with sample data"""
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'doctor_ai'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password')
        )
        cursor = conn.cursor()
        
        print("Checking existing database structure...")
        
        # Check if tables exist and their structure
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"Existing tables: {existing_tables}")
        
        # Drop existing tables in correct order (respecting foreign keys)
        tables_to_drop = ['appointments', 'doctor_schedules', 'patients', 'doctors', 'departments']
        for table in tables_to_drop:
            if table in existing_tables:
                print(f"Dropping existing table: {table}")
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        
        print("Creating fresh database schema...")
        
        # Create departments table
        cursor.execute("""
            CREATE TABLE departments (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ Created departments table")
        
        # Create doctors table
        cursor.execute("""
            CREATE TABLE doctors (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                specialization VARCHAR(100) NOT NULL,
                department_id INTEGER REFERENCES departments(id),
                phone VARCHAR(20),
                email VARCHAR(100),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ Created doctors table")
        
        # Create patients table
        cursor.execute("""
            CREATE TABLE patients (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) UNIQUE NOT NULL,
                email VARCHAR(100),
                date_of_birth DATE,
                gender VARCHAR(10),
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ Created patients table")
        
        # Create doctor_schedules table
        cursor.execute("""
            CREATE TABLE doctor_schedules (
                id SERIAL PRIMARY KEY,
                doctor_id INTEGER REFERENCES doctors(id),
                date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                is_available BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(doctor_id, date, start_time)
            );
        """)
        print("✅ Created doctor_schedules table")
        
        # Create appointments table
        cursor.execute("""
            CREATE TABLE appointments (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients(id),
                doctor_id INTEGER REFERENCES doctors(id),
                appointment_date DATE NOT NULL,
                appointment_time TIME NOT NULL,
                reason TEXT,
                status VARCHAR(20) DEFAULT 'scheduled',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ Created appointments table")
        
        # Insert sample departments
        print("Inserting sample departments...")
        departments = [
            ('Cardiology', 'Heart and cardiovascular care'),
            ('Neurology', 'Brain and nervous system care'),
            ('Orthopedics', 'Bone and joint care'),
            ('Dermatology', 'Skin care'),
            ('General Medicine', 'General health care'),
            ('Pediatrics', 'Children healthcare'),
            ('Gynecology', 'Women healthcare'),
            ('Psychiatry', 'Mental health care')
        ]
        
        for dept_name, dept_desc in departments:
            cursor.execute("""
                INSERT INTO departments (name, description, is_active, created_at) 
                VALUES (%s, %s, %s, %s)
            """, (dept_name, dept_desc, True, datetime.now()))
        
        print("✅ Sample departments inserted")
        
        # Insert sample doctors
        print("Inserting sample doctors...")
        doctors = [
            ('John Smith', 'Cardiologist', 1, '555-0101', 'john.smith@docai.com'),
            ('Sarah Johnson', 'Neurologist', 2, '555-0102', 'sarah.johnson@docai.com'),
            ('Mike Brown', 'Orthopedic Surgeon', 3, '555-0103', 'mike.brown@docai.com'),
            ('Lisa Davis', 'Dermatologist', 4, '555-0104', 'lisa.davis@docai.com'),
            ('David Wilson', 'General Practitioner', 5, '555-0105', 'david.wilson@docai.com'),
            ('Emily Chen', 'Pediatrician', 6, '555-0106', 'emily.chen@docai.com'),
            ('Maria Garcia', 'Gynecologist', 7, '555-0107', 'maria.garcia@docai.com'),
            ('Robert Taylor', 'Psychiatrist', 8, '555-0108', 'robert.taylor@docai.com'),
            ('Jennifer Lee', 'Cardiologist', 1, '555-0109', 'jennifer.lee@docai.com'),
            ('Michael Chen', 'Neurologist', 2, '555-0110', 'michael.chen@docai.com')
        ]
        
        for name, spec, dept_id, phone, email in doctors:
            cursor.execute("""
                INSERT INTO doctors (name, specialization, department_id, phone, email, is_active, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, spec, dept_id, phone, email, True, datetime.now()))
        
        print("✅ Sample doctors inserted")
        
        # Create doctor schedules for next 14 days
        print("Creating doctor schedules...")
        schedule_count = 0
        
        for doctor_id in range(1, 11):  # For all 10 doctors
            for day_offset in range(14):  # Next 14 days
                schedule_date = (datetime.now().date() + timedelta(days=day_offset))
                
                # Skip weekends for most doctors
                if schedule_date.weekday() < 5:  # Monday to Friday
                    # Create multiple time slots per day
                    time_slots = [
                        ('09:00:00', '10:00:00'),
                        ('10:00:00', '11:00:00'),
                        ('11:00:00', '12:00:00'),
                        ('14:00:00', '15:00:00'),  # Afternoon slots
                        ('15:00:00', '16:00:00'),
                        ('16:00:00', '17:00:00')
                    ]
                    
                    for start_time, end_time in time_slots:
                        cursor.execute("""
                            INSERT INTO doctor_schedules (doctor_id, date, start_time, end_time, is_available, created_at) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (doctor_id, schedule_date, start_time, end_time, True, datetime.now()))
                        schedule_count += 1
                
                # Some doctors work weekends (reduced hours)
                elif doctor_id <= 3:  # First 3 doctors work weekends
                    time_slots = [
                        ('10:00:00', '11:00:00'),
                        ('11:00:00', '12:00:00'),
                        ('14:00:00', '15:00:00')
                    ]
                    
                    for start_time, end_time in time_slots:
                        cursor.execute("""
                            INSERT INTO doctor_schedules (doctor_id, date, start_time, end_time, is_available, created_at) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (doctor_id, schedule_date, start_time, end_time, True, datetime.now()))
                        schedule_count += 1
        
        print(f"✅ Created {schedule_count} doctor schedule slots")
        
        # Add a few sample patients for testing
        print("Adding sample patients...")
        sample_patients = [
            ('Test Patient', '9999999999', 'test@example.com'),
            ('Demo User', '8888888888', 'demo@example.com')
        ]
        
        for name, phone, email in sample_patients:
            cursor.execute("""
                INSERT INTO patients (name, phone, email, created_at) 
                VALUES (%s, %s, %s, %s)
            """, (name, phone, email, datetime.now()))
        
        print("✅ Sample patients added")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 Database setup completed successfully!")
        print(f"✅ Created {len(departments)} departments")
        print(f"✅ Created {len(doctors)} doctors")
        print(f"✅ Created {schedule_count} appointment slots")
        print("✅ Database is ready for use!")
        
        # Test database connection
        print("\n🔍 Testing database queries...")
        test_database_queries()
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        import traceback
        traceback.print_exc()

def test_database_queries():
    """Test that our queries work properly"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'doctor_ai'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test departments query
        cursor.execute("SELECT COUNT(*) as count FROM departments WHERE is_active = true")
        dept_count = cursor.fetchone()['count']
        print(f"✅ Departments query: {dept_count} active departments")
        
        # Test doctors query
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM doctors d 
            JOIN departments dep ON d.department_id = dep.id 
            WHERE d.is_active = true
        """)
        doctor_count = cursor.fetchone()['count']
        print(f"✅ Doctors query: {doctor_count} active doctors")
        
        # Test cardiologists query
        cursor.execute("""
            SELECT d.name, d.specialization, dep.name as department
            FROM doctors d
            JOIN departments dep ON d.department_id = dep.id
            WHERE d.is_active = true AND d.specialization ILIKE %s
            ORDER BY d.name
        """, ['%Cardiology%'])
        cardiologists = cursor.fetchall()
        print(f"✅ Cardiologists query: {len(cardiologists)} cardiologists found")
        for doc in cardiologists:
            print(f"   - Dr. {doc['name']} ({doc['specialization']})")
        
        # Test schedules query
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM doctor_schedules 
            WHERE date >= CURRENT_DATE AND is_available = true
        """)
        schedule_count = cursor.fetchone()['count']
        print(f"✅ Schedules query: {schedule_count} available slots")
        
        cursor.close()
        conn.close()
        
        print("✅ All database queries working properly!")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")

if __name__ == "__main__":
    print("🏥 DocAI Database Setup")
    print("=" * 50)
    create_database_schema()