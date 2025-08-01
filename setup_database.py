import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, date
import os
import random
from dotenv import load_dotenv

load_dotenv()

def create_database_schema():
    """Create database tables and populate with sample data"""
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor()
        
        print("🔄 Checking existing database structure...")
        
        # Check if tables exist and their structure
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"   Existing tables: {existing_tables}")
        
        # Drop existing tables in correct order (respecting foreign keys)
        tables_to_drop = ['appointments', 'doctor_availability', 'patients', 'doctors', 'specializations', 'departments']
        for table in tables_to_drop:
            if table in existing_tables:
                print(f"   Dropping existing table: {table}")
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        
        print("🏗️  Creating fresh database schema...")
        
        # Read and execute the schema.sql file
        schema_path = 'schema.sql'
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as schema_file:
                schema_content = schema_file.read()
                
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in schema_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
            
            for statement in statements:
                if statement and not statement.startswith('/*'):
                    try:
                        cursor.execute(statement)
                        print(f"   ✅ Executed: {statement[:50]}...")
                    except Exception as e:
                        print(f"   ⚠️  Warning executing statement: {e}")
        else:
            print("   ❌ schema.sql file not found, creating basic structure...")
            create_basic_schema(cursor)
        
        # Commit all changes
        conn.commit()
        print("✅ Database schema created successfully!")
        
        # Verify the setup
        verify_database_setup(cursor)
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating database schema: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_basic_schema(cursor):
    """Create basic schema if schema.sql is not available"""
    
    print("   Creating basic database structure...")
    
    # Create specializations table
    cursor.execute("""
        CREATE TABLE specializations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("   ✅ Created specializations table")
    
    # Create departments table
    cursor.execute("""
        CREATE TABLE departments (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("   ✅ Created departments table")
    
    # Create doctors table
    cursor.execute("""
        CREATE TABLE doctors (
            id SERIAL PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            phone VARCHAR(20),
            specialization_id INTEGER REFERENCES specializations(id),
            department_id INTEGER REFERENCES departments(id),
            license_number VARCHAR(50) UNIQUE,
            experience_years INTEGER,
            consultation_fee DECIMAL(10,2),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("   ✅ Created doctors table")
    
    # Create patients table
    cursor.execute("""
        CREATE TABLE patients (
            id SERIAL PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            phone VARCHAR(20),
            date_of_birth DATE,
            gender VARCHAR(10),
            address TEXT,
            emergency_contact_name VARCHAR(100),
            emergency_contact_phone VARCHAR(20),
            medical_history TEXT,
            allergies TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("   ✅ Created patients table")
    
    # Create doctor_availability table
    cursor.execute("""
        CREATE TABLE doctor_availability (
            id SERIAL PRIMARY KEY,
            doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
            day_of_week INTEGER NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6),
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            slot_duration INTEGER DEFAULT 30,
            max_patients_per_slot INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT valid_time_range CHECK (start_time < end_time)
        );
    """)
    print("   ✅ Created doctor_availability table")
    
    # Create appointments table
    cursor.execute("""
        CREATE TABLE appointments (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
            doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            duration INTEGER DEFAULT 30,
            status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')),
            reason_for_visit TEXT,
            notes TEXT,
            prescription TEXT,
            follow_up_required BOOLEAN DEFAULT FALSE,
            follow_up_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(doctor_id, appointment_date, appointment_time)
        );
    """)
    print("   ✅ Created appointments table")

def verify_database_setup(cursor):
    """Verify that all tables were created successfully"""
    
    print("\n🔍 Verifying database setup...")
    
    expected_tables = ['specializations', 'departments', 'doctors', 'patients', 'doctor_availability', 'appointments']
    
    for table in expected_tables:
        try:
            # Use parameterized query with psycopg2.sql for safe table name handling
            from psycopg2 import sql
            query = sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
            cursor.execute(query)
            count = cursor.fetchone()[0]
            print(f"   ✅ {table}: {count} records")
        except Exception as e:
            print(f"   ❌ {table}: Error - {e}")
    
    print("✅ Database verification complete!")

def generate_future_random_data():
    """Generate additional random appointment data for the future"""
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n🎲 Generating additional random future data...")
        
        # Get existing data for random selection
        cursor.execute("SELECT id FROM patients")
        patient_ids = [row['id'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM doctors")
        doctor_ids = [row['id'] for row in cursor.fetchall()]
        
        if not patient_ids or not doctor_ids:
            print("   ⚠️  No patients or doctors found. Run full schema setup first.")
            return False
        
        # Generate additional patients for diversity
        additional_patients = [
            ('Emma', 'Thompson', 'emma.thompson@email.com', '555-2001', '1987-05-12', 'Female', '100 Oak St, City, State 12345', 'James Thompson', '555-2002'),
            ('William', 'Johnson', 'william.johnson@email.com', '555-2003', '1969-08-07', 'Male', '200 Pine Ave, City, State 12345', 'Linda Johnson', '555-2004'),
            ('Olivia', 'Brown', 'olivia.brown@email.com', '555-2005', '1993-02-28', 'Female', '300 Maple St, City, State 12345', 'Michael Brown', '555-2006'),
            ('Ethan', 'Davis', 'ethan.davis@email.com', '555-2007', '1981-11-15', 'Male', '400 Cedar Ave, City, State 12345', 'Sarah Davis', '555-2008'),
            ('Sophia', 'Wilson', 'sophia.wilson@email.com', '555-2009', '1976-04-22', 'Female', '500 Elm St, City, State 12345', 'Robert Wilson', '555-2010'),
            ('Mason', 'Garcia', 'mason.garcia@email.com', '555-2011', '1990-09-03', 'Male', '600 Birch Ave, City, State 12345', 'Isabella Garcia', '555-2012'),
            ('Ava', 'Martinez', 'ava.martinez@email.com', '555-2013', '1984-12-18', 'Female', '700 Spruce St, City, State 12345', 'Lucas Martinez', '555-2014'),
            ('Logan', 'Anderson', 'logan.anderson@email.com', '555-2015', '1971-07-09', 'Male', '800 Willow Ave, City, State 12345', 'Mia Anderson', '555-2016'),
            ('Isabella', 'Taylor', 'isabella.taylor@email.com', '555-2017', '1996-01-31', 'Female', '900 Poplar St, City, State 12345', 'Noah Taylor', '555-2018'),
            ('Jacob', 'Thomas', 'jacob.thomas@email.com', '555-2019', '1973-06-26', 'Male', '1000 Aspen Ave, City, State 12345', 'Emma Thomas', '555-2020')
        ]
        
        print("   Adding additional patients...")
        for patient_data in additional_patients:
            try:
                cursor.execute("""
                    INSERT INTO patients (first_name, last_name, email, phone, date_of_birth, gender, address, emergency_contact_name, emergency_contact_phone)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, patient_data)
                print(f"   ✅ Added patient: {patient_data[0]} {patient_data[1]}")
            except Exception as e:
                print(f"   ⚠️  Could not add patient {patient_data[0]} {patient_data[1]}: {e}")
        
        # Refresh patient list
        cursor.execute("SELECT id FROM patients")
        patient_ids = [row['id'] for row in cursor.fetchall()]
        
        # Generate random future appointments (January - June 2026)
        print("   Generating random future appointments...")
        
        appointment_reasons = [
            'Annual checkup', 'Follow-up consultation', 'Routine screening', 'Vaccination',
            'Blood pressure check', 'Diabetes management', 'Weight management', 'Pain assessment',
            'Skin examination', 'Eye examination', 'Hearing test', 'Physical therapy evaluation',
            'Mental health consultation', 'Medication review', 'Lab results discussion',
            'Preventive care', 'Health maintenance', 'Chronic condition management',
            'Injury assessment', 'Second opinion consultation', 'Specialist referral',
            'Pre-operative consultation', 'Post-operative follow-up', 'Treatment planning'
        ]
        
        statuses = ['scheduled', 'confirmed']
        
        # Generate appointments for each month from January to June 2026
        months = [
            ('2026-01', 31), ('2026-02', 28), ('2026-03', 31),
            ('2026-04', 30), ('2026-05', 31), ('2026-06', 30)
        ]
        
        appointments_created = 0
        
        for month_str, days_in_month in months:
            print(f"   Generating appointments for {month_str}...")
            
            # Generate 20-40 appointments per month
            num_appointments = random.randint(20, 40)
            
            for _ in range(num_appointments):
                try:
                    # Random date in the month
                    day = random.randint(1, days_in_month)
                    appointment_date = f"{month_str}-{day:02d}"
                    
                    # Random time during business hours (8 AM - 6 PM)
                    hour = random.randint(8, 17)
                    minute = random.choice([0, 15, 30, 45])
                    appointment_time = f"{hour:02d}:{minute:02d}:00"
                    
                    # Random patient and doctor
                    patient_id = random.choice(patient_ids)
                    doctor_id = random.choice(doctor_ids)
                    
                    # Random duration (15, 30, 45, or 60 minutes)
                    duration = random.choice([15, 30, 45, 60])
                    
                    # Random reason and status
                    reason = random.choice(appointment_reasons)
                    status = random.choice(statuses)
                    
                    # Random notes (sometimes empty)
                    notes_options = [
                        '', 'Patient requested morning appointment', 'Follow-up in 3 months',
                        'Bring previous test results', 'Fasting required', 'New patient',
                        'Insurance pre-authorization obtained', 'Translator needed',
                        'Wheelchair accessible needed', 'Patient prefers afternoon slots'
                    ]
                    notes = random.choice(notes_options)
                    
                    cursor.execute("""
                        INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason_for_visit, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason, notes))
                    
                    appointments_created += 1
                    
                except Exception as e:
                    # Skip if there's a conflict (same doctor, date, time)
                    continue
        
        print(f"   ✅ Created {appointments_created} random future appointments")
        
        # Generate some additional doctor availability for new time slots
        print("   Adding extended doctor availability...")
        
        extended_availability = [
            # Weekend availability for some doctors
            (1, 6, '10:00:00', '14:00:00', 45, 1),  # Dr. Smith - Saturday
            (3, 0, '09:00:00', '12:00:00', 20, 1),  # Dr. Brown - Sunday
            (5, 6, '08:00:00', '12:00:00', 30, 1),  # Dr. Wilson - Saturday
            (6, 0, '10:00:00', '14:00:00', 30, 1),  # Dr. Anderson - Sunday
            # Extended evening hours
            (2, 1, '18:00:00', '21:00:00', 60, 1),  # Dr. Johnson - Monday evening
            (4, 3, '19:00:00', '22:00:00', 60, 1),  # Dr. Davis - Wednesday evening
            (7, 2, '18:00:00', '20:00:00', 30, 1),  # Dr. Lee - Tuesday evening
            (11, 4, '18:00:00', '21:00:00', 60, 1), # Dr. Taylor - Thursday evening
        ]
        
        for availability in extended_availability:
            try:
                cursor.execute("""
                    INSERT INTO doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_duration, max_patients_per_slot)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, availability)
                print(f"   ✅ Added extended availability for doctor {availability[0]}")
            except Exception as e:
                print(f"   ⚠️  Could not add availability: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Random future data generation complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error generating random data: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main setup function"""
    print("🚀 Doc-AI Database Setup & Random Data Generation")
    print("=" * 60)
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found!")
        print("   Using default database connection settings")
        print("   Create a .env file with your database credentials")
    
    # Step 1: Create database schema
    print("\n📋 Step 1: Setting up database schema...")
    if not create_database_schema():
        print("❌ Database schema setup failed!")
        return False
    
    # Step 2: Generate additional random data
    print("\n📋 Step 2: Generating additional random data...")
    if not generate_future_random_data():
        print("❌ Random data generation failed!")
        return False
    
    print("\n✅ Database setup and data generation completed successfully!")
    print("\n📋 Next steps:")
    print("   1. Run: python test_database.py")
    print("   2. Run: python main.py")
    print("   3. Start frontend: cd frontend && npx serve -l 5500 public")
    print("\n📊 Database now contains:")
    print("   • Medical specializations and departments")
    print("   • 12+ doctors with varied schedules")
    print("   • 20+ patients with contact information")
    print("   • Current appointments (July-December 2025)")
    print("   • Random future appointments (January-June 2026)")
    print("   • Extended availability including weekends and evenings")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)