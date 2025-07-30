#!/usr/bin/env python3
"""
Future Data Generator for Doc-AI Hospital Management System
Generates realistic random appointment data for testing and demonstration purposes
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import random
from datetime import datetime, timedelta, date
import os
from dotenv import load_dotenv

load_dotenv()

class FutureDataGenerator:
    def __init__(self):
        self.conn = None
        self.cursor = None
        
        # Realistic medical reasons categorized by specialization
        self.appointment_reasons = {
            'Cardiology': [
                'Chest pain evaluation', 'Heart palpitations', 'Blood pressure check',
                'Cardiac screening', 'Arrhythmia monitoring', 'Stress test',
                'Heart murmur check', 'Hypertension follow-up', 'Cholesterol management',
                'Cardiac medication review', 'Valve disease consultation', 'Heart failure follow-up'
            ],
            'Dermatology': [
                'Skin rash consultation', 'Mole examination', 'Acne treatment',
                'Psoriasis treatment', 'Eczema management', 'Skin cancer screening',
                'Allergic reaction assessment', 'Wart removal', 'Skin biopsy follow-up',
                'Cosmetic consultation', 'Hair loss evaluation', 'Nail disorder treatment'
            ],
            'Pediatrics': [
                'Child wellness check', 'Vaccination', 'Growth assessment',
                'Behavioral concerns', 'Asthma management', 'Ear infection follow-up',
                'Development screening', 'School physical', 'Allergy consultation',
                'ADHD evaluation', 'Sleep disorder assessment', 'Nutrition counseling'
            ],
            'Orthopedics': [
                'Knee pain assessment', 'Back pain evaluation', 'Shoulder injury',
                'Joint replacement consultation', 'Sports injury', 'Arthritis management',
                'Fracture follow-up', 'Physical therapy evaluation', 'Spinal consultation',
                'Hip pain assessment', 'Carpal tunnel evaluation', 'Osteoporosis screening'
            ],
            'Neurology': [
                'Headache consultation', 'Migraine management', 'Seizure evaluation',
                'Memory concerns', 'Parkinson\'s assessment', 'Stroke follow-up',
                'Nerve pain evaluation', 'Tremor assessment', 'Sleep study consultation',
                'Cognitive evaluation', 'Neuropathy management', 'Multiple sclerosis care'
            ],
            'General Medicine': [
                'Annual checkup', 'General health screening', 'Diabetes management',
                'Thyroid function check', 'Weight management', 'Medication review',
                'Preventive care', 'Lab results discussion', 'Chronic condition management',
                'Health maintenance', 'Vaccination', 'Blood work follow-up'
            ],
            'Psychiatry': [
                'Mental health evaluation', 'Depression screening', 'Anxiety consultation',
                'PTSD therapy', 'Medication management', 'Behavioral therapy',
                'Stress management', 'Addiction counseling', 'Mood disorder treatment',
                'Couples therapy', 'Family counseling', 'Crisis intervention'
            ],
            'Gynecology': [
                'Annual women\'s health exam', 'Pregnancy consultation', 'Menopause management',
                'Birth control consultation', 'Fertility evaluation', 'Prenatal care',
                'Hormone therapy', 'PCOS management', 'Contraceptive counseling',
                'Breast examination', 'Pelvic pain evaluation', 'Reproductive health'
            ]
        }
        
        # Additional patient names for diversity
        self.additional_patients = [
            ('Grace', 'Cooper', 'grace.cooper@email.com', '555-3001', '1989-03-14', 'Female'),
            ('Nathan', 'Reed', 'nathan.reed@email.com', '555-3002', '1975-11-28', 'Male'),
            ('Chloe', 'Bailey', 'chloe.bailey@email.com', '555-3003', '1992-07-19', 'Female'),
            ('Ryan', 'Torres', 'ryan.torres@email.com', '555-3004', '1983-01-07', 'Male'),
            ('Zoe', 'Rivera', 'zoe.rivera@email.com', '555-3005', '1986-09-23', 'Female'),
            ('Austin', 'Cook', 'austin.cook@email.com', '555-3006', '1979-05-12', 'Male'),
            ('Lily', 'Ward', 'lily.ward@email.com', '555-3007', '1994-12-03', 'Female'),
            ('Blake', 'Peterson', 'blake.peterson@email.com', '555-3008', '1977-08-16', 'Male'),
            ('Aria', 'Gray', 'aria.gray@email.com', '555-3009', '1991-04-25', 'Female'),
            ('Carson', 'James', 'carson.james@email.com', '555-3010', '1974-10-09', 'Male'),
            ('Hazel', 'Watson', 'hazel.watson@email.com', '555-3011', '1988-06-14', 'Female'),
            ('Jaxon', 'Brooks', 'jaxon.brooks@email.com', '555-3012', '1982-02-27', 'Male'),
            ('Luna', 'Kelly', 'luna.kelly@email.com', '555-3013', '1995-11-18', 'Female'),
            ('Easton', 'Sanders', 'easton.sanders@email.com', '555-3014', '1978-08-05', 'Male'),
            ('Nova', 'Price', 'nova.price@email.com', '555-3015', '1987-03-22', 'Female')
        ]
        
        # Appointment statuses with realistic distribution
        self.status_weights = {
            'scheduled': 0.4,
            'confirmed': 0.5,
            'completed': 0.05,  # Only recent past appointments
            'cancelled': 0.04,
            'no_show': 0.01
        }
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'hospital'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres')
            )
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def add_additional_patients(self):
        """Add more patients for data diversity"""
        print("👥 Adding additional patients...")
        
        added_count = 0
        for patient_data in self.additional_patients:
            try:
                # Generate additional fields
                addresses = [
                    f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Elm', 'Maple'])} {random.choice(['St', 'Ave', 'Blvd', 'Dr'])}, City, State {random.randint(10000, 99999)}",
                ]
                
                emergency_contacts = [
                    ('Emergency Contact', f"555-{random.randint(1000, 9999)}")
                ]
                
                medical_conditions = [
                    '', 'Hypertension', 'Diabetes Type 2', 'Asthma', 'Allergies', 
                    'High cholesterol', 'Anxiety', 'Depression', 'Arthritis'
                ]
                
                allergies_list = [
                    '', 'Penicillin', 'Shellfish', 'Peanuts', 'Latex', 'Pollen', 'Dust mites'
                ]
                
                self.cursor.execute("""
                    INSERT INTO patients (first_name, last_name, email, phone, date_of_birth, gender, 
                                        address, emergency_contact_name, emergency_contact_phone,
                                        medical_history, allergies)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    patient_data[0], patient_data[1], patient_data[2], patient_data[3],
                    patient_data[4], patient_data[5],
                    random.choice(addresses),
                    f"{patient_data[0]} Emergency",
                    f"555-{random.randint(1000, 9999)}",
                    random.choice(medical_conditions),
                    random.choice(allergies_list)
                ))
                added_count += 1
                print(f"   ✅ Added: {patient_data[0]} {patient_data[1]}")
                
            except Exception as e:
                print(f"   ⚠️  Could not add {patient_data[0]} {patient_data[1]}: {e}")
        
        self.conn.commit()
        print(f"✅ Added {added_count} additional patients")
        return added_count
    
    def get_database_entities(self):
        """Retrieve existing patients and doctors for random assignment"""
        # Get all patients
        self.cursor.execute("SELECT id FROM patients WHERE is_active = true")
        patient_ids = [row['id'] for row in self.cursor.fetchall()]
        
        # Get all doctors with their specializations
        self.cursor.execute("""
            SELECT d.id, s.name as specialization
            FROM doctors d
            JOIN specializations s ON d.specialization_id = s.id
            WHERE d.is_active = true
        """)
        doctors = [(row['id'], row['specialization']) for row in self.cursor.fetchall()]
        
        return patient_ids, doctors
    
    def generate_appointment_time_slots(self):
        """Generate realistic appointment time slots"""
        # Common appointment times (every 15 minutes during business hours)
        time_slots = []
        for hour in range(8, 18):  # 8 AM to 6 PM
            for minute in [0, 15, 30, 45]:
                time_slots.append(f"{hour:02d}:{minute:02d}:00")
        return time_slots
    
    def get_weighted_status(self, appointment_date):
        """Get appointment status based on date and realistic weights"""
        today = date.today()
        
        if appointment_date < today:
            # Past appointments should be mostly completed or no-show
            return random.choices(['completed', 'no_show', 'cancelled'], 
                                weights=[0.85, 0.10, 0.05])[0]
        elif appointment_date == today:
            # Today's appointments
            return random.choices(['confirmed', 'scheduled', 'completed'], 
                                weights=[0.6, 0.3, 0.1])[0]
        else:
            # Future appointments
            return random.choices(['scheduled', 'confirmed'], 
                                weights=[0.4, 0.6])[0]
    
    def generate_future_appointments(self, months_ahead=12, appointments_per_month=50):
        """Generate realistic future appointments"""
        print(f"📅 Generating appointments for the next {months_ahead} months...")
        
        patient_ids, doctors = self.get_database_entities()
        time_slots = self.generate_appointment_time_slots()
        
        if not patient_ids or not doctors:
            print("❌ No patients or doctors found in database")
            return 0
        
        total_generated = 0
        today = date.today()
        
        for month_offset in range(months_ahead):
            # Calculate target month
            target_month = today.replace(day=1) + timedelta(days=32 * month_offset)
            target_month = target_month.replace(day=1)
            
            # Get last day of the month
            if target_month.month == 12:
                next_month = target_month.replace(year=target_month.year + 1, month=1)
            else:
                next_month = target_month.replace(month=target_month.month + 1)
            
            last_day = (next_month - timedelta(days=1)).day
            
            print(f"   Generating for {target_month.strftime('%B %Y')}...")
            
            month_appointments = 0
            attempts = 0
            max_attempts = appointments_per_month * 3  # Prevent infinite loops
            
            while month_appointments < appointments_per_month and attempts < max_attempts:
                attempts += 1
                
                try:
                    # Generate random appointment details
                    day = random.randint(1, last_day)
                    appointment_date = target_month.replace(day=day)
                    
                    # Skip weekends for most appointments (90% weekdays)
                    if appointment_date.weekday() >= 5 and random.random() < 0.9:
                        continue
                    
                    appointment_time = random.choice(time_slots)
                    patient_id = random.choice(patient_ids)
                    doctor_id, specialization = random.choice(doctors)
                    
                    # Choose reason based on specialization
                    if specialization in self.appointment_reasons:
                        reason = random.choice(self.appointment_reasons[specialization])
                    else:
                        reason = random.choice(self.appointment_reasons['General Medicine'])
                    
                    # Duration based on specialization
                    duration_mapping = {
                        'Psychiatry': [60, 90],
                        'Neurology': [45, 60],
                        'Orthopedics': [30, 45, 60],
                        'Cardiology': [30, 45],
                        'Pediatrics': [15, 20, 30],
                        'General Medicine': [15, 30],
                        'Dermatology': [20, 30],
                        'Gynecology': [30, 45]
                    }
                    
                    if specialization in duration_mapping:
                        duration = random.choice(duration_mapping[specialization])
                    else:
                        duration = random.choice([15, 30, 45])
                    
                    # Get status based on date
                    status = self.get_weighted_status(appointment_date)
                    
                    # Generate notes (30% chance of having notes)
                    notes_options = [
                        '', '', '', '',  # 70% empty
                        'Patient requested morning appointment',
                        'Follow-up in 3 months',
                        'Bring previous test results',
                        'Fasting required',
                        'New patient',
                        'Insurance pre-authorization obtained',
                        'Translator requested',
                        'Follow-up from previous visit',
                        'Referral from primary care',
                        'Second opinion requested'
                    ]
                    notes = random.choice(notes_options)
                    
                    # Insert appointment
                    self.cursor.execute("""
                        INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, 
                                                duration, status, reason_for_visit, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (patient_id, doctor_id, appointment_date, appointment_time, 
                          duration, status, reason, notes))
                    
                    month_appointments += 1
                    total_generated += 1
                    
                except Exception as e:
                    # Skip conflicts or other issues
                    continue
            
            print(f"      ✅ Generated {month_appointments} appointments")
        
        self.conn.commit()
        print(f"✅ Generated {total_generated} total appointments")
        return total_generated
    
    def add_extended_doctor_availability(self):
        """Add extended hours and weekend availability for some doctors"""
        print("⏰ Adding extended doctor availability...")
        
        # Get current doctors
        self.cursor.execute("SELECT id FROM doctors WHERE is_active = true")
        doctor_ids = [row['id'] for row in self.cursor.fetchall()]
        
        extended_slots = [
            # Weekend availability (some doctors)
            {'days': [6], 'start': '09:00:00', 'end': '13:00:00', 'duration': 30},  # Saturday morning
            {'days': [0], 'start': '10:00:00', 'end': '14:00:00', 'duration': 45},  # Sunday afternoon
            # Extended evening hours
            {'days': [1, 3, 5], 'start': '18:00:00', 'end': '20:00:00', 'duration': 30},  # Mon, Wed, Fri evenings
            {'days': [2, 4], 'start': '17:30:00', 'end': '19:30:00', 'duration': 45},   # Tue, Thu evenings
            # Early morning slots
            {'days': [1, 2, 3, 4, 5], 'start': '07:00:00', 'end': '08:00:00', 'duration': 30},  # Early mornings
        ]
        
        added_count = 0
        
        for doctor_id in doctor_ids:
            # Each doctor gets 1-2 extended slots randomly
            num_slots = random.randint(0, 2)
            selected_slots = random.sample(extended_slots, min(num_slots, len(extended_slots)))
            
            for slot in selected_slots:
                for day in slot['days']:
                    try:
                        self.cursor.execute("""
                            INSERT INTO doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_duration, max_patients_per_slot)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (doctor_id, day, slot['start'], slot['end'], slot['duration'], 1))
                        added_count += 1
                        
                    except Exception as e:
                        # Skip if slot already exists
                        continue
        
        self.conn.commit()
        print(f"✅ Added {added_count} extended availability slots")
        return added_count
    
    def generate_seasonal_patterns(self):
        """Generate seasonal appointment patterns (flu season, back-to-school, etc.)"""
        print("🌟 Adding seasonal appointment patterns...")
        
        patient_ids, doctors = self.get_database_entities()
        
        # Flu season appointments (October - March)
        flu_season_appointments = [
            ('Flu vaccination', 'General Medicine', '2025-10-01', '2025-11-30'),
            ('Cold symptoms', 'General Medicine', '2025-11-01', '2026-02-28'),
            ('Respiratory issues', 'General Medicine', '2025-12-01', '2026-03-31'),
        ]
        
        # Back-to-school physicals (July - September)
        school_physicals = [
            ('School physical', 'Pediatrics', '2025-07-01', '2025-09-30'),
            ('Sports physical', 'General Medicine', '2025-07-15', '2025-09-15'),
        ]
        
        # Holiday stress counseling (November - January)
        holiday_stress = [
            ('Holiday stress management', 'Psychiatry', '2025-11-15', '2026-01-15'),
            ('Seasonal depression', 'Psychiatry', '2025-12-01', '2026-02-28'),
        ]
        
        seasonal_patterns = flu_season_appointments + school_physicals + holiday_stress
        
        generated_count = 0
        
        for reason, specialization, start_date, end_date in seasonal_patterns:
            # Find doctors with matching specialization
            matching_doctors = [d for d in doctors if d[1] == specialization]
            if not matching_doctors:
                continue
            
            # Generate 5-15 appointments for each seasonal pattern
            for _ in range(random.randint(5, 15)):
                try:
                    # Random date within the seasonal period
                    start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    
                    days_diff = (end - start).days
                    random_days = random.randint(0, days_diff)
                    appointment_date = start + timedelta(days=random_days)
                    
                    # Random appointment time
                    hour = random.randint(8, 17)
                    minute = random.choice([0, 15, 30, 45])
                    appointment_time = f"{hour:02d}:{minute:02d}:00"
                    
                    # Random patient and matching doctor
                    patient_id = random.choice(patient_ids)
                    doctor_id = random.choice(matching_doctors)[0]
                    
                    # Standard duration for seasonal appointments
                    duration = 30
                    status = self.get_weighted_status(appointment_date)
                    
                    self.cursor.execute("""
                        INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time,
                                                duration, status, reason_for_visit, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (patient_id, doctor_id, appointment_date, appointment_time, 
                          duration, status, reason, 'Seasonal appointment'))
                    
                    generated_count += 1
                    
                except Exception as e:
                    continue
        
        self.conn.commit()
        print(f"✅ Generated {generated_count} seasonal appointments")
        return generated_count
    
    def update_existing_appointments(self):
        """Update some existing appointments with more realistic data"""
        print("🔄 Updating existing appointments with enhanced data...")
        
        # Add prescription data to completed appointments
        prescription_examples = [
            'Prescribed medication as discussed during visit',
            'Continue current medication regimen',
            'Ibuprofen 400mg twice daily for 7 days',
            'Follow-up blood work ordered',
            'Physical therapy referral provided',
            'Specialist referral to cardiology',
            'No prescription needed at this time',
            'Medication dosage adjusted',
            'Lab work ordered - return in 2 weeks',
            'Imaging studies recommended'
        ]
        
        # Add follow-up requirements
        self.cursor.execute("""
            UPDATE appointments 
            SET prescription = %s,
                follow_up_required = true,
                follow_up_date = appointment_date + INTERVAL '30 days'
            WHERE status = 'completed' 
            AND prescription IS NULL
            AND random() < 0.6
        """, (random.choice(prescription_examples),))
        
        updated_completed = self.cursor.rowcount
        
        # Add detailed notes to appointments without notes
        detailed_notes = [
            'Patient reports improvement since last visit',
            'Vital signs stable, no immediate concerns',
            'Discussed lifestyle modifications',
            'Patient education provided',
            'Symptoms have resolved since last visit',
            'Routine follow-up, no new concerns',
            'Medication compliance discussed',
            'Patient satisfied with treatment progress',
            'No adverse reactions reported',
            'Continue current treatment plan'
        ]
        
        self.cursor.execute("""
            UPDATE appointments 
            SET notes = %s
            WHERE (notes IS NULL OR notes = '')
            AND status IN ('completed', 'confirmed')
            AND random() < 0.4
        """, (random.choice(detailed_notes),))
        
        updated_notes = self.cursor.rowcount
        
        self.conn.commit()
        print(f"✅ Updated {updated_completed} completed appointments with prescriptions")
        print(f"✅ Updated {updated_notes} appointments with detailed notes")
        
        return updated_completed + updated_notes

def main():
    """Main function to run the future data generation"""
    print("🎲 Doc-AI Future Data Generation Tool")
    print("=" * 50)
    
    generator = FutureDataGenerator()
    
    if not generator.connect():
        print("❌ Failed to connect to database")
        return False
    
    try:
        print("\n📊 Current database status check...")
        
        # Check current data counts
        generator.cursor.execute("SELECT COUNT(*) as count FROM patients")
        patient_count = generator.cursor.fetchone()['count']
        
        generator.cursor.execute("SELECT COUNT(*) as count FROM appointments")
        appointment_count = generator.cursor.fetchone()['count']
        
        generator.cursor.execute("SELECT COUNT(*) as count FROM doctor_availability")
        availability_count = generator.cursor.fetchone()['count']
        
        print(f"   Current patients: {patient_count}")
        print(f"   Current appointments: {appointment_count}")
        print(f"   Current availability slots: {availability_count}")
        
        # Generate additional data
        total_additions = 0
        
        print("\n🔄 Generating additional data...")
        
        # Step 1: Add more patients
        added_patients = generator.add_additional_patients()
        total_additions += added_patients
        
        # Step 2: Add extended doctor availability
        added_availability = generator.add_extended_doctor_availability()
        total_additions += added_availability
        
        # Step 3: Generate future appointments (next 12 months)
        future_appointments = generator.generate_future_appointments(
            months_ahead=12, 
            appointments_per_month=60
        )
        total_additions += future_appointments
        
        # Step 4: Add seasonal patterns
        seasonal_appointments = generator.generate_seasonal_patterns()
        total_additions += seasonal_appointments
        
        # Step 5: Update existing appointments
        updated_appointments = generator.update_existing_appointments()
        total_additions += updated_appointments
        
        # Final status check
        print("\n📊 Final database status...")
        
        generator.cursor.execute("SELECT COUNT(*) as count FROM patients")
        final_patient_count = generator.cursor.fetchone()['count']
        
        generator.cursor.execute("SELECT COUNT(*) as count FROM appointments")
        final_appointment_count = generator.cursor.fetchone()['count']
        
        generator.cursor.execute("""
            SELECT COUNT(*) as future_appointments
            FROM appointments 
            WHERE appointment_date > CURRENT_DATE
        """)
        future_count = generator.cursor.fetchone()['future_appointments']
        
        print(f"   Final patients: {final_patient_count} (+{final_patient_count - patient_count})")
        print(f"   Final appointments: {final_appointment_count} (+{final_appointment_count - appointment_count})")
        print(f"   Future appointments: {future_count}")
        
        # Generate monthly breakdown
        generator.cursor.execute("""
            SELECT DATE_TRUNC('month', appointment_date) as month,
                   COUNT(*) as count
            FROM appointments
            WHERE appointment_date >= CURRENT_DATE
            GROUP BY DATE_TRUNC('month', appointment_date)
            ORDER BY month
            LIMIT 12
        """)
        
        monthly_breakdown = generator.cursor.fetchall()
        
        print("\n📅 Future appointments by month:")
        for month_data in monthly_breakdown:
            month_str = month_data['month'].strftime('%Y-%m')
            print(f"   {month_str}: {month_data['count']} appointments")
        
        print(f"\n✅ Data generation complete!")
        print(f"   Total additions/updates: {total_additions}")
        print("\n📋 Next steps:")
        print("   1. Run: python test_database.py")
        print("   2. Test the application with: python main.py")
        print("   3. The database now has realistic data for the next 12 months")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during data generation: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        generator.disconnect()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)