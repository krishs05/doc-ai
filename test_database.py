import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

def test_database_connection():
    """Test database connection and basic queries"""
    try:
        # Test connection
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("🔗 Database connection successful!")
        
        # List all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        print(f"📋 Tables in database: {[t['table_name'] for t in tables]}")
        
        # Test each table
        for table in tables:
            table_name = table['table_name']
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count = cursor.fetchone()['count']
            print(f"   {table_name}: {count} records")
        
        # Test specific queries used by the app
        print("\n🧪 Testing application queries...")
        
        # Test specializations (not departments)
        cursor.execute("SELECT id, name FROM specializations ORDER BY name")
        specializations = cursor.fetchall()
        print(f"✅ Active specializations: {len(specializations)}")
        for spec in specializations:
            print(f"   - {spec['name']}")
        
        # Test doctors with specializations (corrected query)
        cursor.execute("""
            SELECT d.id, 
                   CONCAT(d.first_name, ' ', d.last_name) as name, 
                   s.name as specialization, 
                   d.experience_years,
                   d.consultation_fee
            FROM doctors d
            JOIN specializations s ON d.specialization_id = s.id
            WHERE d.is_active = true
            ORDER BY s.name, d.last_name
            LIMIT 5
        """)
        doctors = cursor.fetchall()
        print(f"\n✅ Sample doctors: {len(doctors)}")
        for doc in doctors:
            print(f"   - Dr. {doc['name']} ({doc['specialization']}, {doc['experience_years']} years, ${doc['consultation_fee']})")
        
        # Test patients
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM patients 
            WHERE is_active = true
        """)
        patient_count = cursor.fetchone()['count']
        print(f"\n✅ Active patients: {patient_count}")
        
        # Test doctor availability schedules
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM doctor_availability da
            WHERE da.is_active = true
        """)
        availability_count = cursor.fetchone()['count']
        print(f"✅ Doctor availability slots: {availability_count}")
        
        # Test appointments
        cursor.execute("""
            SELECT a.id, 
                   a.appointment_date, 
                   a.appointment_time, 
                   a.status,
                   CONCAT(p.first_name, ' ', p.last_name) as patient_name,
                   CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                   s.name as specialization
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN specializations s ON d.specialization_id = s.id
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
            LIMIT 3
        """)
        appointments = cursor.fetchall()
        print(f"\n✅ Sample appointments: {len(appointments)}")
        for apt in appointments:
            print(f"   - {apt['appointment_date']} at {apt['appointment_time']}: {apt['patient_name']} → Dr. {apt['doctor_name']} ({apt['specialization']}) [{apt['status']}]")
        
        # Test if both departments and specializations exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('departments', 'specializations')
        """)
        related_tables = [row['table_name'] for row in cursor.fetchall()]
        
        if 'departments' in related_tables and 'specializations' in related_tables:
            print(f"\n⚠️  Warning: Both 'departments' and 'specializations' tables exist!")
            print("   The application should use one consistent table for medical specialties.")
            
            # Check departments table structure
            cursor.execute("SELECT COUNT(*) as count FROM departments")
            dept_count = cursor.fetchone()['count']
            print(f"   - departments: {dept_count} records")
            
            # Check if doctors table references departments or specializations
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'doctors' 
                AND column_name IN ('department_id', 'specialization_id')
            """)
            doctor_refs = [row['column_name'] for row in cursor.fetchall()]
            print(f"   - doctors table references: {doctor_refs}")
        
        # Test the main queries that the application will use
        print(f"\n🔍 Testing main application queries...")
        
        # Query that main.py uses for doctors
        cursor.execute("""
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
        LIMIT 3
        """)
        app_doctors = cursor.fetchall()
        print(f"✅ Main.py doctor query works: {len(app_doctors)} doctors")
        
        # Query that main.py uses for appointments
        cursor.execute("""
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
        LIMIT 3
        """)
        app_appointments = cursor.fetchall()
        print(f"✅ Main.py appointment query works: {len(app_appointments)} appointments")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Database is ready for use!")
        print("\n📋 Summary:")
        print(f"   ✓ {len(specializations)} medical specializations")
        print(f"   ✓ {len(doctors)} active doctors")
        print(f"   ✓ {patient_count} active patients")
        print(f"   ✓ {availability_count} doctor availability slots")
        print(f"   ✓ {len(appointments)} recent appointments")
        print(f"   ✓ All main application queries working")
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_database_schema():
    """Analyze the database schema to understand the structure"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n🔍 Database Schema Analysis:")
        print("=" * 50)
        
        # Get detailed table information
        tables_info = ['doctors', 'specializations', 'departments', 'appointments', 'patients']
        
        for table in tables_info:
            try:
                # Check if table exists
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = %s
                """, (table,))
                
                if cursor.fetchone():
                    print(f"\n📋 Table: {table}")
                    
                    # Get column information
                    cursor.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns 
                        WHERE table_name = %s AND table_schema = 'public'
                        ORDER BY ordinal_position
                    """, (table,))
                    
                    columns = cursor.fetchall()
                    for col in columns[:5]:  # Show first 5 columns
                        null_info = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                        print(f"   - {col['column_name']}: {col['data_type']} ({null_info})")
                    
                    if len(columns) > 5:
                        print(f"   ... and {len(columns) - 5} more columns")
                        
                else:
                    print(f"\n❌ Table '{table}' does not exist")
                    
            except Exception as e:
                print(f"\n❌ Error analyzing table '{table}': {e}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Schema analysis failed: {e}")

if __name__ == "__main__":
    success = test_database_connection()
    if success:
        analyze_database_schema()
    else:
        print("\n🔧 Please fix database issues before proceeding")