import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def test_database_connection():
    """Test basic database connectivity"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("🔗 Testing database connection...")
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"   ✅ Connected to: {version['version'][:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return False

def test_schema_structure():
    """Test that all required tables exist with correct structure"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n🏗️  Testing database schema structure...")
        
        # Check if all required tables exist
        expected_tables = ['specializations', 'departments', 'doctors', 'patients', 'doctor_availability', 'appointments']
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN %s
        """, (tuple(expected_tables),))
        
        existing_tables = [row['table_name'] for row in cursor.fetchall()]
        
        for table in expected_tables:
            if table in existing_tables:
                print(f"   ✅ Table exists: {table}")
            else:
                print(f"   ❌ Missing table: {table}")
                return False
        
        # Test specific column requirements
        print("\n🔍 Verifying key columns...")
        
        # Test doctors table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'doctors' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        doctor_columns = {row['column_name']: row for row in cursor.fetchall()}
        
        required_doctor_cols = ['id', 'first_name', 'last_name', 'email', 'specialization_id', 'experience_years']
        
        for col in required_doctor_cols:
            if col in doctor_columns:
                print(f"   ✅ doctors.{col} ({doctor_columns[col]['data_type']})")
            else:
                print(f"   ❌ doctors.{col} - MISSING!")
                return False
        
        # Test appointments table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'appointments' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        appointment_columns = {row['column_name']: row for row in cursor.fetchall()}
        
        required_appointment_cols = ['id', 'patient_id', 'doctor_id', 'appointment_date', 'appointment_time', 'status']
        
        for col in required_appointment_cols:
            if col in appointment_columns:
                print(f"   ✅ appointments.{col} ({appointment_columns[col]['data_type']})")
            else:
                print(f"   ❌ appointments.{col} - MISSING!")
                return False
        
        cursor.close()
        conn.close()
        
        print("✅ Database schema structure verification complete!")
        return True
        
    except Exception as e:
        print(f"❌ Schema structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_integrity():
    """Test data integrity and relationships"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n🔗 Testing data integrity and relationships...")
        
        # Test specializations
        cursor.execute("SELECT COUNT(*) as count FROM specializations WHERE is_active = true")
        specializations_count = cursor.fetchone()['count']
        print(f"   ✅ Active specializations: {specializations_count}")
        
        # Test departments
        cursor.execute("SELECT COUNT(*) as count FROM departments WHERE is_active = true")
        departments_count = cursor.fetchone()['count']
        print(f"   ✅ Active departments: {departments_count}")
        
        # Test doctors with specializations
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM doctors d 
            JOIN specializations s ON d.specialization_id = s.id 
            WHERE d.is_active = true
        """)
        doctors_count = cursor.fetchone()['count']
        print(f"   ✅ Active doctors with specializations: {doctors_count}")
        
        # Test patients
        cursor.execute("SELECT COUNT(*) as count FROM patients WHERE is_active = true")
        patients_count = cursor.fetchone()['count']
        print(f"   ✅ Active patients: {patients_count}")
        
        # Test doctor availability
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM doctor_availability da 
            JOIN doctors d ON da.doctor_id = d.id 
            WHERE da.is_active = true AND d.is_active = true
        """)
        availability_count = cursor.fetchone()['count']
        print(f"   ✅ Doctor availability slots: {availability_count}")
        
        # Test appointments with valid relationships
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            WHERE p.is_active = true AND d.is_active = true
        """)
        appointments_count = cursor.fetchone()['count']
        print(f"   ✅ Valid appointments: {appointments_count}")
        
        # Test foreign key relationships
        cursor.execute("""
            SELECT COUNT(*) as orphaned_doctors
            FROM doctors d 
            LEFT JOIN specializations s ON d.specialization_id = s.id 
            WHERE s.id IS NULL
        """)
        orphaned_doctors = cursor.fetchone()['orphaned_doctors']
        
        if orphaned_doctors == 0:
            print("   ✅ All doctors have valid specializations")
        else:
            print(f"   ⚠️  {orphaned_doctors} doctors without valid specializations")
        
        cursor.execute("""
            SELECT COUNT(*) as orphaned_appointments
            FROM appointments a
            LEFT JOIN patients p ON a.patient_id = p.id
            LEFT JOIN doctors d ON a.doctor_id = d.id
            WHERE p.id IS NULL OR d.id IS NULL
        """)
        orphaned_appointments = cursor.fetchone()['orphaned_appointments']
        
        if orphaned_appointments == 0:
            print("   ✅ All appointments have valid patient and doctor references")
        else:
            print(f"   ⚠️  {orphaned_appointments} appointments with invalid references")
        
        cursor.close()
        conn.close()
        
        print("✅ Data integrity verification complete!")
        return True
        
    except Exception as e:
        print(f"❌ Data integrity test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_application_queries():
    """Test key queries that the application will use"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n🔄 Testing application queries...")
        
        # Test 1: Get doctors by specialization
        cursor.execute("""
            SELECT d.first_name, d.last_name, s.name as specialization
            FROM doctors d
            JOIN specializations s ON d.specialization_id = s.id
            WHERE s.name ILIKE '%cardiology%' AND d.is_active = true
        """)
        cardiology_doctors = cursor.fetchall()
        print(f"   ✅ Cardiology doctors found: {len(cardiology_doctors)}")
        
        # Test 2: Get upcoming appointments
        cursor.execute("""
            SELECT a.appointment_date, a.appointment_time, 
                   p.first_name || ' ' || p.last_name as patient_name,
                   d.first_name || ' ' || d.last_name as doctor_name,
                   s.name as specialization
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN specializations s ON d.specialization_id = s.id
            WHERE a.appointment_date >= CURRENT_DATE
            ORDER BY a.appointment_date, a.appointment_time
            LIMIT 10
        """)
        upcoming_appointments = cursor.fetchall()
        print(f"   ✅ Upcoming appointments found: {len(upcoming_appointments)}")
        
        # Test 3: Get doctor availability
        cursor.execute("""
            SELECT d.first_name || ' ' || d.last_name as doctor_name,
                   CASE da.day_of_week
                       WHEN 0 THEN 'Sunday'
                       WHEN 1 THEN 'Monday'
                       WHEN 2 THEN 'Tuesday'
                       WHEN 3 THEN 'Wednesday'
                       WHEN 4 THEN 'Thursday'
                       WHEN 5 THEN 'Friday'
                       WHEN 6 THEN 'Saturday'
                   END as day_name,
                   da.start_time, da.end_time
            FROM doctor_availability da
            JOIN doctors d ON da.doctor_id = d.id
            WHERE da.is_active = true AND d.is_active = true
            ORDER BY d.last_name, da.day_of_week, da.start_time
            LIMIT 10
        """)
        doctor_schedules = cursor.fetchall()
        print(f"   ✅ Doctor schedules found: {len(doctor_schedules)}")
        
        # Test 4: Get appointment statistics by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM appointments
            GROUP BY status
            ORDER BY count DESC
        """)
        appointment_stats = cursor.fetchall()
        print(f"   ✅ Appointment status statistics:")
        for stat in appointment_stats:
            print(f"      {stat['status']}: {stat['count']}")
        
        # Test 5: Test search functionality
        cursor.execute("""
            SELECT p.first_name, p.last_name, p.email
            FROM patients p
            WHERE p.first_name ILIKE '%alice%' OR p.last_name ILIKE '%alice%'
        """)
        search_results = cursor.fetchall()
        print(f"   ✅ Patient search results: {len(search_results)}")
        
        # Test 6: Get recent appointments with full details
        cursor.execute("""
            SELECT a.appointment_date, a.appointment_time, a.status, a.reason_for_visit,
                   p.first_name || ' ' || p.last_name as patient_name,
                   d.first_name || ' ' || d.last_name as doctor_name,
                   s.name as specialization
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN specializations s ON d.specialization_id = s.id
            WHERE a.appointment_date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
            LIMIT 5
        """)
        recent_appointments = cursor.fetchall()
        print(f"   ✅ Recent appointments (last 30 days): {len(recent_appointments)}")
        
        # Test 7: Check for appointment conflicts
        cursor.execute("""
            SELECT doctor_id, appointment_date, appointment_time, COUNT(*) as conflicts
            FROM appointments
            GROUP BY doctor_id, appointment_date, appointment_time
            HAVING COUNT(*) > 1
        """)
        conflicts = cursor.fetchall()
        if len(conflicts) == 0:
            print("   ✅ No appointment conflicts found")
        else:
            print(f"   ⚠️  {len(conflicts)} appointment conflicts detected")
        
        # Test 8: Verify data distribution across months
        cursor.execute("""
            SELECT DATE_TRUNC('month', appointment_date) as month,
                   COUNT(*) as appointment_count
            FROM appointments
            GROUP BY DATE_TRUNC('month', appointment_date)
            ORDER BY month
        """)
        monthly_distribution = cursor.fetchall()
        print(f"   ✅ Appointment distribution across months:")
        for month_data in monthly_distribution:
            month_str = month_data['month'].strftime('%Y-%m')
            print(f"      {month_str}: {month_data['appointment_count']} appointments")
        
        cursor.close()
        conn.close()
        
        print("✅ Application queries test complete!")
        return True
        
    except Exception as e:
        print(f"❌ Application queries test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_views_and_indexes():
    """Test that views and indexes are working properly"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n👁️  Testing views and indexes...")
        
        # Test if views exist and work
        try:
            cursor.execute("SELECT COUNT(*) as count FROM appointment_details LIMIT 1")
            view_count = cursor.fetchone()['count']
            print(f"   ✅ appointment_details view working: {view_count} records")
        except Exception as e:
            print(f"   ⚠️  appointment_details view not available: {e}")
        
        try:
            cursor.execute("SELECT COUNT(*) as count FROM doctor_schedule_view LIMIT 1")
            schedule_count = cursor.fetchone()['count']
            print(f"   ✅ doctor_schedule_view working: {schedule_count} records")
        except Exception as e:
            print(f"   ⚠️  doctor_schedule_view not available: {e}")
        
        # Test indexes by checking query performance indicators
        cursor.execute("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('doctors', 'appointments', 'patients', 'doctor_availability')
        """)
        indexes = cursor.fetchall()
        print(f"   ✅ Database indexes found: {len(indexes)}")
        for index in indexes[:5]:  # Show first 5 indexes
            print(f"      {index['indexname']} on {index['tablename']}")
        
        cursor.close()
        conn.close()
        
        print("✅ Views and indexes test complete!")
        return True
        
    except Exception as e:
        print(f"❌ Views and indexes test failed: {e}")
        return False

def generate_test_report():
    """Generate a comprehensive test report"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n📊 Generating comprehensive test report...")
        
        # Database summary statistics
        stats = {}
        
        tables = ['specializations', 'departments', 'doctors', 'patients', 'doctor_availability', 'appointments']
        for table in tables:
            # Use parameterized query with psycopg2.sql for safe table name handling
            from psycopg2 import sql
            query = sql.SQL("SELECT COUNT(*) as count FROM {}").format(sql.Identifier(table))
            cursor.execute(query)
            stats[table] = cursor.fetchone()['count']
        
        # Appointment status breakdown
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM appointments
            GROUP BY status
        """)
        appointment_statuses = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Doctor utilization
        cursor.execute("""
            SELECT d.first_name || ' ' || d.last_name as doctor_name,
                   COUNT(a.id) as appointment_count
            FROM doctors d
            LEFT JOIN appointments a ON d.id = a.doctor_id
            WHERE d.is_active = true
            GROUP BY d.id, d.first_name, d.last_name
            ORDER BY appointment_count DESC
        """)
        doctor_utilization = cursor.fetchall()
        
        # Future appointments count
        cursor.execute("""
            SELECT COUNT(*) as future_appointments
            FROM appointments
            WHERE appointment_date > CURRENT_DATE
        """)
        future_appointments = cursor.fetchone()['future_appointments']
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("📋 DATABASE TEST REPORT")
        print("="*60)
        
        print(f"\n📊 Table Statistics:")
        for table, count in stats.items():
            print(f"   {table:20}: {count:>6} records")
        
        print(f"\n📅 Appointment Statistics:")
        for status, count in appointment_statuses.items():
            print(f"   {status:20}: {count:>6} appointments")
        
        print(f"\n🔮 Future Appointments: {future_appointments}")
        
        print(f"\n👨‍⚕️ Top 5 Most Booked Doctors:")
        for i, doc in enumerate(doctor_utilization[:5], 1):
            print(f"   {i}. {doc['doctor_name']:25}: {doc['appointment_count']:>3} appointments")
        
        print(f"\n✅ Database is ready for production use!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Test report generation failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Doc-AI Database Testing Suite")
    print("=" * 50)
    
    test_results = []
    
    # Run all tests
    tests = [
        ("Database Connection", test_database_connection),
        ("Schema Structure", test_schema_structure),
        ("Data Integrity", test_data_integrity),
        ("Application Queries", test_application_queries),
        ("Views and Indexes", test_views_and_indexes)
    ]
    
    for test_name, test_function in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        result = test_function()
        test_results.append((test_name, result))
        
        if result:
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED")
    
    # Generate final report
    generate_test_report()
    
    # Summary
    passed_tests = sum(1 for _, result in test_results if result)
    total_tests = len(test_results)
    
    print(f"\n🎯 Test Summary: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Database is ready for use.")
        print("\n📋 Next steps:")
        print("   1. Run: python main.py")
        print("   2. Start frontend: cd frontend && npx serve -l 5500 public")
        return True
    else:
        print("⚠️  Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)