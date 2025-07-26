import psycopg2
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

def populate_sample_data():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    cursor = conn.cursor()
    
    # Insert departments
    departments = [
        ('Cardiology', 'Heart and cardiovascular care'),
        ('Neurology', 'Brain and nervous system care'),
        ('Orthopedics', 'Bone and joint care'),
        ('Dermatology', 'Skin care'),
        ('General Medicine', 'General health care')
    ]
    
    for dept in departments:
        cursor.execute(
            "INSERT INTO departments (name, description, is_active, created_at) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING",
            (dept[0], dept[1], True, datetime.now())
        )
    
    # Insert doctors
    doctors = [
        ('John Smith', 'Cardiologist', 1, '555-0101'),
        ('Sarah Johnson', 'Neurologist', 2, '555-0102'),
        ('Mike Brown', 'Orthopedic Surgeon', 3, '555-0103'),
        ('Lisa Davis', 'Dermatologist', 4, '555-0104'),
        ('David Wilson', 'General Practitioner', 5, '555-0105')
    ]
    
    for doctor in doctors:
        cursor.execute(
            "INSERT INTO doctors (name, specialization, department_id, phone, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (phone) DO NOTHING",
            (doctor[0], doctor[1], doctor[2], doctor[3], True, datetime.now())
        )
    
    # Insert doctor schedules for next 7 days
    for doctor_id in range(1, 6):
        for day in range(7):
            date = datetime.now().date() + timedelta(days=day)
            cursor.execute(
                "INSERT INTO doctor_schedules (doctor_id, date, start_time, end_time, is_available, created_at) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (doctor_id, date, start_time) DO NOTHING",
                (doctor_id, date, '09:00:00', '17:00:00', True, datetime.now())
            )
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Sample data populated successfully!")

if __name__ == "__main__":
    populate_sample_data()