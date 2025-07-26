#!/usr/bin/env python3
"""
Database Setup Script for Doc-AI
This script initializes the database using the schema.sql file
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import subprocess
import sys

load_dotenv()

def run_schema_sql():
    """Run the schema.sql file to set up the database"""
    try:
        # Database connection parameters
        db_host = os.getenv('DB_HOST', 'localhost')
        db_name = os.getenv('DB_NAME', 'hospital')
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', 'postgres')
        
        print("🔄 Setting up database schema using schema.sql...")
        print(f"📍 Connecting to: {db_host}/{db_name} as {db_user}")
        
        # Read and execute schema.sql
        with open('schema.sql', 'r', encoding='utf-8') as f:
            schema_content = f.read()
        
        # Connect to database
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password
        )
        
        # Set autocommit for DDL operations
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("📋 Executing schema.sql...")
        
        # Execute the schema file
        cursor.execute(schema_content)
        
        print("✅ Schema executed successfully!")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_name = t.table_name AND table_schema = 'public') as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"\n📊 Created {len(tables)} tables:")
        for table_name, col_count in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            print(f"   ✓ {table_name}: {col_count} columns, {row_count} rows")
        
        cursor.close()
        conn.close()
        
        return True
        
    except FileNotFoundError:
        print("❌ Error: schema.sql file not found!")
        print("   Make sure schema.sql exists in the current directory")
        return False
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure PostgreSQL is running")
        print("   2. Check database credentials in .env file")
        print("   3. Ensure database exists: createdb hospital")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_database_structure():
    """Test that the database structure matches what the application expects"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'hospital'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n🧪 Testing database structure...")
        
        # Test expected tables exist
        expected_tables = ['specializations', 'doctors', 'patients', 'doctor_availability', 'appointments']
        for table in expected_tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()['count']
            print(f"   ✓ {table}: {count} records")
        
        # Test key columns exist
        print("\n🔍 Verifying key columns...")
        
        # Test doctors table structure
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'doctors' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        doctor_columns = [row['column_name'] for row in cursor.fetchall()]
        required_doctor_cols = ['id', 'first_name', 'last_name', 'email', 'specialization_id', 'experience_years']
        
        for col in required_doctor_cols:
            if col in doctor_columns:
                print(f"   ✓ doctors.{col}")
            else:
                print(f"   ❌ doctors.{col} - MISSING!")
        
        # Test appointments table structure
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'appointments' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        appointment_columns = [row['column_name'] for row in cursor.fetchall()]
        required_appointment_cols = ['id', 'patient_id', 'doctor_id', 'appointment_date', 'appointment_time']
        
        for col in required_appointment_cols:
            if col in appointment_columns:
                print(f"   ✓ appointments.{col}")
            else:
                print(f"   ❌ appointments.{col} - MISSING!")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Database structure verification complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing database structure: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Doc-AI Database Setup")
    print("=" * 40)
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found!")
        print("   Using default database connection settings")
    
    # Check if schema.sql exists
    if not os.path.exists('schema.sql'):
        print("❌ Error: schema.sql file not found!")
        print("   Please ensure schema.sql is in the current directory")
        return False
    
    # Run schema setup
    if not run_schema_sql():
        return False
    
    # Test database structure
    if not test_database_structure():
        return False
    
    print("\n✅ Database setup completed successfully!")
    print("\n📋 Next steps:")
    print("   1. Run: python test_database.py")
    print("   2. Run: python main.py")
    print("   3. Start frontend: cd frontend && npx serve -l 5500 public")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)