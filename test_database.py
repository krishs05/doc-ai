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
            database=os.getenv('DB_NAME', 'doctor_ai'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password')
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
        
        # Test departments
        cursor.execute("SELECT id, name FROM departments WHERE is_active = true")
        departments = cursor.fetchall()
        print(f"✅ Active departments: {len(departments)}")
        
        # Test doctors with departments
        cursor.execute("""
            SELECT d.id, d.name, d.specialization, dep.name as department
            FROM doctors d
            JOIN departments dep ON d.department_id = dep.id
            WHERE d.is_active = true
            LIMIT 3
        """)
        doctors = cursor.fetchall()
        print(f"✅ Sample doctors: {len(doctors)}")
        for doc in doctors:
            print(f"   - Dr. {doc['name']} ({doc['specialization']}, {doc['department']})")
        
        # Test available schedules
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM doctor_schedules ds
            WHERE ds.date >= CURRENT_DATE
            AND ds.is_available = true
        """)
        schedules = cursor.fetchone()['count']
        print(f"✅ Available appointment slots: {schedules}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Database is ready for use!")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_database_connection()